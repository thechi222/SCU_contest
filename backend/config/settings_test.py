import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-" + "0" * 40)

from config.settings import *  # noqa: E402,F403

# 測試不執行 collectstatic;改為即時掃描,避免 WhiteNoise 因 STATIC_ROOT 不存在而警告
WHITENOISE_AUTOREFRESH = True
