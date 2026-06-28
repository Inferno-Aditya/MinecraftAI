import unittest
import os
from fastapi.testclient import TestClient
from main import app
from personality import PERSONALITY_FILE, DEFAULT_PERSONALITY, load_personality, restore_default_personality

class TestPersonalityAPI(unittest.TestCase):
    def setUp(self):
        # Backup existing personality.md if it exists
        self.personality_backup = None
        if os.path.exists(PERSONALITY_FILE):
            try:
                with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
                    self.personality_backup = f.read()
            except Exception:
                pass
        
        # Reset to default for testing
        restore_default_personality()
        self.client = TestClient(app)

    def tearDown(self):
        # Restore backed up personality.md
        if self.personality_backup is not None:
            try:
                with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
                    f.write(self.personality_backup)
            except Exception:
                pass
        else:
            if os.path.exists(PERSONALITY_FILE):
                try:
                    os.remove(PERSONALITY_FILE)
                except Exception:
                    pass

    def test_get_personality(self):
        """Test retrieving the current personality content and metadata."""
        response = self.client.get("/api/personality")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["content"], DEFAULT_PERSONALITY)
        self.assertEqual(data["word_count"], len(DEFAULT_PERSONALITY.split()))
        self.assertEqual(data["char_count"], len(DEFAULT_PERSONALITY))
        self.assertTrue(len(data["last_modified"]) > 0)

    def test_update_personality_success(self):
        """Test saving a valid new personality."""
        new_text = "You are a redstone engineer companion."
        response = self.client.post("/api/personality", json={"content": new_text})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})
        
        # Verify read
        self.assertEqual(load_personality(), new_text)

    def test_update_personality_empty_error(self):
        """Test that updating with an empty or whitespace-only personality is rejected."""
        response = self.client.post("/api/personality", json={"content": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be empty", response.json()["detail"])
        
        # Verify personality is unchanged (still default)
        self.assertEqual(load_personality(), DEFAULT_PERSONALITY)

    def test_reset_personality(self):
        """Test resetting the personality back to default."""
        # Update first
        self.client.post("/api/personality", json={"content": "Custom text"})
        
        # Reset
        response = self.client.post("/api/personality/reset")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(response.json()["content"], DEFAULT_PERSONALITY)
        
        # Verify load returns default
        self.assertEqual(load_personality(), DEFAULT_PERSONALITY)
