import unittest
import os
import time
import json
from unittest.mock import patch, MagicMock
from resource_manager import (
    resource_manager,
    execute_llm_request_with_rate_limits,
    estimate_tokens,
    is_rate_limit_exception
)
from config import load_config, save_config, save_api_key

class TestResourceManager(unittest.TestCase):
    def setUp(self):
        # Clear stats before tests
        resource_manager.tracker.history = []
        resource_manager.tracker.daily_history = {}
        
        # Reset session statistics
        resource_manager.statistics.session_requests = 0
        resource_manager.statistics.session_success = 0
        resource_manager.statistics.session_failure = 0
        resource_manager.statistics.session_input_tokens = 0
        resource_manager.statistics.session_output_tokens = 0
        resource_manager.statistics.session_retries = 0
        resource_manager.statistics.session_latencies = []

    def test_token_estimation(self):
        text = "Hello world of Minecraft"
        # 24 chars / 4 = 6 tokens
        self.assertEqual(estimate_tokens(text), 6)

    def test_rate_limit_exception_detection(self):
        self.assertTrue(is_rate_limit_exception(Exception("429 Too Many Requests")))
        self.assertTrue(is_rate_limit_exception(Exception("ResourceExhausted quota exceeded")))
        self.assertFalse(is_rate_limit_exception(Exception("Connection Timeout")))

    @patch("resource_manager.get_provider")
    def test_successful_request_telemetry(self, mock_get_provider):
        # Mock provider generate return value
        mock_provider = MagicMock()
        mock_provider.generate.return_value = '{"reply": "test response"}'
        mock_provider.last_usage_metadata = {"prompt_tokens": 15, "completion_tokens": 5}
        mock_get_provider.return_value = mock_provider

        response = execute_llm_request_with_rate_limits(
            provider_name="mock",
            model_name="mock-model",
            system_prompt="System Prompt",
            user_prompt="User Prompt"
        )

        self.assertEqual(response, '{"reply": "test response"}')
        stats = resource_manager.get_stats()
        
        # Verify telemetry
        self.assertEqual(stats["requests_today"], 1)
        self.assertEqual(stats["requests_session"], 1)
        self.assertEqual(stats["input_tokens_session"], 15)
        self.assertEqual(stats["output_tokens_session"], 5)
        self.assertEqual(stats["total_tokens_session"], 20)
        self.assertEqual(stats["successful_requests_session"], 1)
        self.assertEqual(stats["failed_requests_session"], 0)

    @patch("resource_manager.get_provider")
    def test_rate_limit_backoff_and_retry(self, mock_get_provider):
        # Mock provider to raise 429 on first attempt, succeed on second
        mock_provider = MagicMock()
        calls = []
        def side_effect(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise Exception("429 Rate Limit Exceeded")
            return '{"reply": "success after retry"}'
        mock_provider.generate.side_effect = side_effect
        mock_provider.last_usage_metadata = {"prompt_tokens": 10, "completion_tokens": 5}
        mock_get_provider.return_value = mock_provider

        # Mock time.sleep to avoid actual delays in tests
        with patch("time.sleep") as mock_sleep:
            response = execute_llm_request_with_rate_limits(
                provider_name="mock",
                model_name="mock-model",
                system_prompt="System Prompt",
                user_prompt="User Prompt"
            )

            self.assertEqual(response, '{"reply": "success after retry"}')
            mock_sleep.assert_called_once_with(2.0) # Check first retry delay of 2.0s
            
            stats = resource_manager.get_stats()
            self.assertEqual(stats["requests_session"], 1) # counts as one planned request flow
            self.assertEqual(stats["retry_count"], 1) # one retry attempt
            self.assertEqual(stats["successful_requests_session"], 1)

    @patch("resource_manager.get_provider")
    def test_failed_request_telemetry(self, mock_get_provider):
        # Mock provider to raise an exception
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = Exception("General LLM Error")
        mock_get_provider.return_value = mock_provider

        with self.assertRaises(Exception):
            execute_llm_request_with_rate_limits(
                provider_name="mock",
                model_name="mock-model",
                system_prompt="System",
                user_prompt="User"
            )

        stats = resource_manager.get_stats()
        self.assertEqual(stats["requests_session"], 1)
        self.assertEqual(stats["successful_requests_session"], 0)
        self.assertEqual(stats["failed_requests_session"], 1)

    def test_launcher_heartbeat_tracking(self):
        # Status initially inactive
        resource_manager.monitor.last_launcher_heartbeat = 0.0
        self.assertEqual(resource_manager.get_stats()["launcher_status"], "Inactive (Not Connected)")
        
        # Record heartbeat
        resource_manager.record_launcher_heartbeat()
        self.assertEqual(resource_manager.get_stats()["launcher_status"], "Active (Connected)")

if __name__ == "__main__":
    unittest.main()
