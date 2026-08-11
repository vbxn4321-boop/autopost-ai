"""
config.py — 환경변수 및 전역 설정
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Pillow 10+에서 Image.ANTIALIAS가 제거됐지만 moviepy==1.0.3이 여전히 참조한다 —
# config.py는 영상 처리 모듈들보다 먼저 임포트되므로 여기서 호환 shim을 걸어둔다.
from PIL import Image as _PILImage
if not hasattr(_PILImage, "ANTIALIAS"):
    _PILImage.ANTIALIAS = _PILImage.LANCZOS

# ─── 기본 경로 설정 ─────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
BGM_DIR = BASE_DIR / "static" / "assets" / "bgm"

# 필요 디렉토리 자동 생성
for d in [UPLOAD_DIR, OUTPUT_DIR, DATA_DIR]:
    d.mkdir(exist_ok=True)

# ─── Gemini API (무료) ────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-flash-latest"   # 구글 최신 무료 티어 모델 자동 연결

# ─── OpenAI 설정 (미사용) ───────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o-mini"

# ─── Whisper 설정 (로컬 STT) ─────────────────────────────────
WHISPER_MODEL = "base"                 # base / small / medium / large
WHISPER_LANGUAGE = "ko"               # 한국어

# ─── Meta (Instagram/Facebook) Graph API ─────────────────────
# 앱 자격증명 — 실제 발행에 필요한 페이지/IG 액세스 토큰은 /auth/meta/login OAuth 로그인으로 발급됨
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")

# 인스타그램 media API는 image_url/video_url에 공개적으로 접근 가능한 절대 URL이 필요하다
# (localhost는 메타 서버가 접근할 수 없으므로 배포된 Render 주소를 기본값으로 사용)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://autopost-ai-bcwk.onrender.com")

# ─── Naver API ───────────────────────────────────────────────
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")

# ─── OAuth 콜백 URI (네이버/틱톡/메타 로그인 연동용) ────────────
NAVER_REDIRECT_URI = "https://autopost-ai-bcwk.onrender.com/auth/naver/callback"
TIKTOK_REDIRECT_URI = "https://autopost-ai-bcwk.onrender.com/auth/tiktok/callback"
META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "https://autopost-ai-bcwk.onrender.com/auth/meta/callback")

# ─── X (Twitter) API ─────────────────────────────────────────
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

# ─── TikTok API ──────────────────────────────────────────────
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")

# ─── Flask 설정 ──────────────────────────────────────────────
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
FLASK_DEBUG = os.getenv("FLASK_ENV", "development") == "development"

# ─── 파일 업로드 설정 ────────────────────────────────────────
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a"}
MAX_UPLOAD_SIZE_MB = 200              # 최대 200MB

# ─── 수익 모델(플랜) 설정 ────────────────────────────────────────
PLANS = {
    "FREE": {
        "max_generations_per_day": 9999,
        "watermark_removal": False,
    },
    "PRO": {
        "max_generations_per_day": 9999,
        "watermark_removal": True,
    }
}

# ─── 플랫폼별 설정 ───────────────────────────────────────────
PLATFORM_SETTINGS = {
    "instagram": {
        "name": "인스타그램",
        "emoji": "📸",
        "max_caption_chars": 2200,
        "recommended_chars": 150,
        "max_hashtags": 30,
        "video_resolution": (1080, 1920),
        "video_aspect": "9:16",
    },
    "tiktok": {
        "name": "틱톡",
        "emoji": "🎵",
        "max_caption_chars": 2200,
        "recommended_chars": 50,
        "max_hashtags": 10,
        "video_resolution": (1080, 1920),
        "video_aspect": "9:16",
    },

    "naver_blog": {
        "name": "네이버 블로그",
        "emoji": "📝",
        "max_caption_chars": 10000,
        "recommended_chars": 1000,
        "max_hashtags": 10,
        "video_resolution": (1080, 1080),
        "video_aspect": "1:1",
    },
    "facebook": {
        "name": "페이스북",
        "emoji": "📘",
        "max_caption_chars": 63206,
        "recommended_chars": 400,
        "max_hashtags": 5,
        "video_resolution": (1080, 1080),
        "video_aspect": "1:1",
    },
    "x_twitter": {
        "name": "X (트위터)",
        "emoji": "🐦",
        "max_caption_chars": 280,
        "recommended_chars": 150,
        "max_hashtags": 3,
        "video_resolution": (1080, 1080),
        "video_aspect": "1:1",
    },
    "threads": {
        "name": "스레드",
        "emoji": "🧵",
        "max_caption_chars": 500,
        "recommended_chars": 150,
        "max_hashtags": 1,
        "video_resolution": (1080, 1920),
        "video_aspect": "9:16",
    },
}

# ─── DB 설정 ─────────────────────────────────────────────────
DB_PATH = DATA_DIR / "posts.db"
