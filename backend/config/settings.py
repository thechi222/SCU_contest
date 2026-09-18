import mimetypes
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent
FRONTEND_DIR = REPO_DIR / "frontend"

load_dotenv(REPO_DIR / ".env")

# Windows 登錄檔可能將 .js 對應為 text/plain,導致瀏覽器拒絕載入 ES module
mimetypes.add_type("text/javascript", ".js", True)


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY and DEBUG:
    SECRET_KEY = "django-insecure-local-development-only"
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure")):
    raise ImproperlyConfigured("DJANGO_DEBUG=0 時必須設定長度至少 50 字元的 DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# 設定了 HTTPS 來源即視為以 HTTPS 對外服務,session 與 CSRF cookie 只經 HTTPS 傳送
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = any(
    origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
    ),
}

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True

# 使用者上傳與成果檔案。不經 MEDIA_URL 直接對外,一律由通過權限檢查的 view 提供
MEDIA_ROOT = Path(os.environ.get("DJANGO_DATA_DIR", BASE_DIR / "data")).resolve()

# 派工參數(README §4.5)
LEASE_SECONDS = 20.0            # 一次派工的租約長度
HEARTBEAT_SECONDS = 5.0         # Agent 心跳間隔
MAX_JOB_ATTEMPTS = 3            # 含首次執行,最多三次
NODE_OFFLINE_SECONDS = 30       # 超過此秒數沒有心跳即視為未開放

# 上傳限制(README §4.4)
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_BATCH_FILES = 20
MAX_BATCH_BYTES = 150 * 1024 * 1024
MAX_IMAGE_SIZE = (2048, 2048)   # 放大任務的原圖尺寸上限

STATIC_URL = "static/"
STATICFILES_DIRS = [FRONTEND_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
    },
}
