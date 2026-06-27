import unittest
import os
import json
from unittest.mock import patch, MagicMock

from model_manager import model_manager, ModelProfile
from providers import get_provider
from resource_manager import resource_manager
from main import app
from fastapi.testclient import TestClient

class TestModelManager(unittest.TestCase):
    def setUp(self):
        self.config_backup = None
        from config import CONFIG_FILE
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config_backup = f.read()
            except Exception:
                pass

        # Backup cache file
        self.cache_backup = None
        from model_manager import DISCOVERED_CACHE_FILE
        if os.path.exists(DISCOVERED_CACHE_FILE):
            try:
                with open(DISCOVERED_CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache_backup = f.read()
            except Exception:
                pass

        # Clear tracking stats for clean test runs
        resource_manager.tracker.model_stats.clear()
        
        # Reset model manager to use fresh cache/bootstrap values
        model_manager.discover_models(force=False)

    def tearDown(self):
        from config import CONFIG_FILE
        if self.config_backup is not None:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    f.write(self.config_backup)
            except Exception:
                pass
        else:
            if os.path.exists(CONFIG_FILE):
                try:
                    os.remove(CONFIG_FILE)
                except Exception:
                    pass

        # Restore cache file
        from model_manager import DISCOVERED_CACHE_FILE
        if self.cache_backup is not None:
            try:
                with open(DISCOVERED_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(self.cache_backup)
            except Exception:
                pass
        else:
            if os.path.exists(DISCOVERED_CACHE_FILE):
                try:
                    os.remove(DISCOVERED_CACHE_FILE)
                except Exception:
                    pass

        # Reset model manager again
        model_manager.discover_models(force=False)

    def test_supported_models_loaded(self):
        models = model_manager.get_supported_models()
        self.assertIn("gemini-2.5-flash", models)
        self.assertIn("gemini-3.1-flash-lite", models)
        self.assertIn("gemini-5.5-flash", models)
        self.assertIn("mock-model", models)
        
        profile = models["gemini-5.5-flash"]
        self.assertEqual(profile.provider, "gemini")
        self.assertEqual(profile.rpm, 15)

    def test_model_switching_and_hot_reload(self):
        # Validate initial model
        model_manager.set_active_model("mock-model")
        self.assertEqual(model_manager.get_active_model(), "mock-model")
        self.assertEqual(model_manager.get_active_provider(), "mock")

        # Test hot reload by switching to gemini-3.1-flash-lite
        success = model_manager.set_active_model("gemini-3.1-flash-lite")
        self.assertTrue(success)
        self.assertEqual(model_manager.get_active_model(), "gemini-3.1-flash-lite")
        self.assertEqual(model_manager.get_active_provider(), "gemini")

        # Verify rate limits were copied to system config
        from config import load_config
        sys_config = load_config()
        self.assertEqual(sys_config["providers"]["gemini"]["rate_limits"]["requests_per_minute"], 30)

        # Switch to invalid model
        success_invalid = model_manager.set_active_model("non-existent-model")
        self.assertFalse(success_invalid)

    def test_provider_resolves_active_model(self):
        model_manager.set_active_model("mock-model")
        provider = get_provider()
        self.assertEqual(provider.model_name, "mock-model")

        model_manager.set_active_model("gemini-2.5-flash")
        provider_gemini = get_provider()
        self.assertEqual(provider_gemini.model_name, "gemini-2.5-flash")

    def test_per_model_telemetry(self):
        model = "gemini-5.5-flash"
        
        # Record normal request
        resource_manager.tracker.record_request(
            provider="gemini",
            model=model,
            input_tokens=100,
            output_tokens=50,
            latency=1.5,
            success=True
        )
        
        # Record failed request
        resource_manager.tracker.record_request(
            provider="gemini",
            model=model,
            input_tokens=100,
            output_tokens=0,
            latency=0.5,
            success=False,
            error_msg="Overloaded"
        )

        # Record tool success and failure
        resource_manager.record_tool_execution(model, success=True)
        resource_manager.record_tool_execution(model, success=False)

        # Record rate limit event
        resource_manager.record_rate_limit_event(model)

        stats = resource_manager.get_stats()
        benchmarks = stats["model_benchmarks"]
        self.assertIn(model, benchmarks)
        
        model_bench = benchmarks[model]
        self.assertEqual(model_bench["requests"], 2)
        self.assertEqual(model_bench["success_rate"], 50.0)
        self.assertEqual(model_bench["average_latency"], 1.5) # calculated from successes
        self.assertEqual(model_bench["average_prompt_tokens"], 100.0)
        self.assertEqual(model_bench["tool_success_rate"], 50.0)
        self.assertEqual(model_bench["rate_limit_events"], 1)
        self.assertIn("Overloaded", model_bench["recent_errors"])

    def test_rest_api_endpoints(self):
        client = TestClient(app)
        
        # Test GET /api/models
        response = client.get("/api/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("active_model", data)
        self.assertIn("supported_models", data)
        self.assertIn("gemini-2.5-flash", data["supported_models"])
        self.assertIn("default_model", data)
        self.assertIn("last_sync_time", data)

        # Test POST /api/models/active
        response_post = client.post("/api/models/active", json={"model_id": "mock-model"})
        self.assertEqual(response_post.status_code, 200)
        self.assertEqual(response_post.json()["active_model"], "mock-model")

        # Test POST /api/models/refresh
        response_ref = client.post("/api/models/refresh")
        self.assertEqual(response_ref.status_code, 200)
        self.assertIn("supported_models", response_ref.json())

        # Verify dynamic providers list GET /api/providers
        resp_prov = client.get("/api/providers")
        self.assertEqual(resp_prov.status_code, 200)
        providers = resp_prov.json()
        
        gemini_prov = next(p for p in providers if p["id"] == "gemini")
        self.assertIn("gemini-2.5-flash", gemini_prov["models"])
        self.assertIn("gemini-3.1-flash-lite", gemini_prov["models"])

    def test_default_model_resolution(self):
        # Remove active model config to test first launch default
        from config import load_config, save_config, CONFIG_FILE
        if os.path.exists(CONFIG_FILE):
            try:
                os.remove(CONFIG_FILE)
            except Exception:
                pass
        
        # Verify it falls back to Gemma 4
        self.assertEqual(model_manager.get_active_model(), "gemma-4-31b-it")

    def test_fallback_during_sync(self):
        # Set active model to a model that will be removed during sync
        model_manager.set_active_model("gemini-2.5-flash")
        self.assertEqual(model_manager.get_active_model(), "gemini-2.5-flash")

        # Mock list_models to return ONLY gemma-4-31b-it (removing gemini-2.5-flash)
        mock_model = MagicMock()
        mock_model.name = "models/gemma-4-31b-it"
        mock_model.display_name = "Gemma 4 32B"
        mock_model.description = "Mocked Gemma"
        mock_model.supported_generation_methods = ["generateContent"]
        
        with patch("google.generativeai.list_models", return_value=[mock_model]):
            res = model_manager.discover_models(force=True)
            self.assertTrue(res["active_model_changed"])
            self.assertIn("no longer available", res["warning"])
            
            # Active model should have gracefully fell back to the default Gemma 4
            self.assertEqual(model_manager.get_active_model(), "gemma-4-31b-it")
