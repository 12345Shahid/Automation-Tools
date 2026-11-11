import os
from pathlib import Path
from dotenv import load_dotenv

# Load root .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# LLM Providers Configuration
DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "moonmath")
MOONMATH_API_KEY = os.getenv("MOONMATH_API_KEY", "")
MOONMATH_BASE_URL = os.getenv("MOONMATH_BASE_URL", "https://zro.moonmath.ai/v1")
MOONMATH_MODEL = os.getenv("MOONMATH_MODEL", "deepseek-v4.1-flash")

APINEX_API_KEY = os.getenv("APINEX_API_KEY", "")
APINEX_BASE_URL = os.getenv("APINEX_BASE_URL", "https://api.apinex.bond/v1")
APINEX_MODEL = os.getenv("APINEX_MODEL", "deepseek-v4.1-flash")

KIE_API_KEY = os.getenv("KIE_API_KEY", "")
KIE_BASE_URL = os.getenv("KIE_BASE_URL", "https://api.kie.ai/openai/v1")
KIE_MODEL = os.getenv("KIE_MODEL", "deepseek-v4-1-flash")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Video Specs (YouTube Shorts / Reels / TikTok)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Assets & Storage Paths
ASSETS_DIR = PROJECT_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
AUDIO_DIR = ASSETS_DIR / "audio"
DEFAULT_FONT = FONTS_DIR / "font.ttf"
DEFAULT_BGM = AUDIO_DIR / "lofi_ambient.mp3"
POP_SFX = AUDIO_DIR / "pop.wav"
WHOOSH_SFX = AUDIO_DIR / "whoosh.wav"

OUTPUT_DIR = PROJECT_ROOT / "content_engine" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# TTS Voices
DEFAULT_VOICE = "en-US-ChristopherNeural"
AVAILABLE_VOICES = {
    "christopher": "en-US-ChristopherNeural",   # Energetic, authoritative male
    "eric": "en-US-EricNeural",                 # Conversational, deep male
    "jenny": "en-US-JennyNeural",               # Clear, professional female
    "sonia": "en-GB-SoniaNeural",               # British female, refined
    "ryan": "en-GB-RyanNeural"                  # British male
}
