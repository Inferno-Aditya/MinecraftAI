import unittest
import os
import shutil
from request_context import RequestContext
from eval_recorder import record_evaluation

class TestEvalRecorder(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.evals_dir = os.path.join(self.base_dir, "..", "evals")
        self.recorded_dirs = []

    def tearDown(self):
        # Clean up any created directories during the test
        for d in self.recorded_dirs:
            if os.path.exists(d):
                shutil.rmtree(d)

    def test_record_evaluation_success(self):
        ctx = RequestContext("Test evaluation query?")
        ctx.request_id = "TESTID12"
        # Mock created_at timestamp: 2024-06-28 20:32:31 local time (1719586951 epoch)
        ctx.created_at = 1719586951.0  
        ctx.provider_name = "mock-provider"
        ctx.model_name = "mock-model"
        ctx.plan_strategy = "KNOWLEDGE"
        ctx.intent = "KNOWLEDGE"
        ctx.response_time_ms = 120.0
        ctx.planner_system_prompt = "System prompt content"
        ctx.planner_user_prompt = "User prompt content"
        ctx.planner_raw_response = '{"reply": "mock response", "response_strategy": "KNOWLEDGE", "tool_calls": []}'
        
        player_state = {
            "player_info": {
                "name": "TestPlayer",
                "x": 100,
                "y": 64,
                "z": 200
            }
        }
        
        # Base64 for 1x1 transparent PNG
        screenshot_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        response_reply = "Final synthesized reply answer."
        
        record_evaluation(ctx, player_state, screenshot_b64, response_reply)
        
        # Resolve path using local time formatting output of recorder
        import time
        local_time = time.localtime(ctx.created_at)
        formatted_time = time.strftime("%Y-%m-%d_%H-%M-%S", local_time)
        req_folder_name = f"{formatted_time}_REQ-TESTID12"
        expected_folder = os.path.join(self.evals_dir, req_folder_name)
        self.recorded_dirs.append(expected_folder)
        
        self.assertTrue(os.path.exists(expected_folder))
        
        # Verify individual files exist
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "question.txt")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "answer.txt")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "player_state.json")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "planner.json")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "tools.json")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "timings.json")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "raw_llm_response.json")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "request.json")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "screenshot.png")))
        self.assertTrue(os.path.exists(os.path.join(expected_folder, "README.md")))
        
        # Verify content of question
        with open(os.path.join(expected_folder, "question.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Test evaluation query?")

        # Verify content of answer
        with open(os.path.join(expected_folder, "answer.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Final synthesized reply answer.")

        # Verify readme matches expectation
        with open(os.path.join(expected_folder, "README.md"), "r", encoding="utf-8") as f:
            readme_text = f.read()
            self.assertIn("**Question**: Test evaluation query?", readme_text)
            self.assertIn("**Final Answer**: Final synthesized reply answer.", readme_text)
            self.assertIn("**Time Taken**: 120.0 ms", readme_text)

if __name__ == "__main__":
    unittest.main()
