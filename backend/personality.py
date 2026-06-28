import os
import logging

logger = logging.getLogger("Backend.Personality")

DEFAULT_PERSONALITY = (
    "You are Aditya's Minecraft companion.\n"
    "Your goal is to help the player enjoy Minecraft while remaining accurate, calm, and useful.\n"
    "Behave like an experienced teammate rather than a search engine.\n"
    "Use live game information whenever available.\n"
    "Combine Minecraft knowledge with the current game state.\n"
    "Celebrate achievements naturally.\n"
    "Warn the player about danger when appropriate.\n"
    "Avoid unnecessary explanations.\n"
    "Never invent information.\n"
    "If you do not know something, say so honestly.\n"
    "Prioritize helping the player accomplish their goals rather than simply answering questions."
)

PERSONALITY_FILE = os.path.join(os.path.dirname(__file__), "data", "personality.md")

def ensure_personality_exists():
    """Ensures the personality file and its parent directories exist, populating with defaults if missing."""
    data_dir = os.path.dirname(PERSONALITY_FILE)
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {data_dir}: {e}")
            
    if not os.path.exists(PERSONALITY_FILE):
        try:
            with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_PERSONALITY)
            logger.info("Created default personality file.")
        except Exception as e:
            logger.error(f"Failed to write default personality file: {e}")

def load_personality() -> str:
    """Loads the personality from disk. If missing, empty, or corrupt, returns default and auto-heals."""
    ensure_personality_exists()
    try:
        if os.path.exists(PERSONALITY_FILE):
            with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                return content
            logger.warning("Personality file was empty. Falling back to default.")
    except Exception as e:
        logger.error(f"Failed to read personality file: {e}. Falling back to default.")
    return DEFAULT_PERSONALITY

def save_personality(content: str) -> bool:
    """Saves the personality to disk. Prevents empty personalities."""
    content_stripped = content.strip()
    if not content_stripped:
        logger.warning("Attempted to save empty personality. Blocked.")
        return False
    ensure_personality_exists()
    try:
        with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
            f.write(content_stripped)
        logger.info("Saved personality successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to save personality: {e}")
        return False

def restore_default_personality() -> str:
    """Overwrites the personality file with the default content and returns it."""
    ensure_personality_exists()
    try:
        with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_PERSONALITY)
        logger.info("Restored default personality.")
        return DEFAULT_PERSONALITY
    except Exception as e:
        logger.error(f"Failed to restore default personality: {e}")
        return DEFAULT_PERSONALITY

def get_personality_meta() -> dict:
    """Returns metadata for the personality file: word count, character count, last modified."""
    ensure_personality_exists()
    try:
        content = load_personality()
        stat = os.stat(PERSONALITY_FILE)
        import datetime
        last_modified = datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat()
        return {
            "content": content,
            "word_count": len(content.split()),
            "char_count": len(content),
            "last_modified": last_modified
        }
    except Exception as e:
        logger.error(f"Failed to retrieve personality metadata: {e}")
        return {
            "content": DEFAULT_PERSONALITY,
            "word_count": len(DEFAULT_PERSONALITY.split()),
            "char_count": len(DEFAULT_PERSONALITY),
            "last_modified": ""
        }
