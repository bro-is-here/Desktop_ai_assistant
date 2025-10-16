# config.py

# ===== API KEYS =====
# Get from https://platform.openai.com/account/api-keys
OPENAI_API_KEYS = [
    "sk-proj-YOUR-KEY-1-HERE",
    "sk-proj-YOUR-KEY-2-HERE",
    "sk-proj-YOUR-KEY-3-HERE",
]

# Or single key fallback:
OPENAI_API_KEY = "sk-proj-YOUR-KEY-HERE"

# ===== VOICE SETTINGS =====
# Use offline PocketSphinx
USE_POCKETSPHINX = True

# Default TTS model: "pyttsx3" (offline) or "edge" (online)
DEFAULT_TTS_MODEL = "pyttsx3"

# Speech rate (100-300, default 190)
PYTTSX3_RATE = 190

# ===== OTHER SETTINGS =====
WAKE_WORD = "robin"
DEFAULT_PERSONALITY = "professional"
ENABLE_TTS = True
ENABLE_VOICE = True
ENABLE_PERFORMANCE_MONITOR = True
