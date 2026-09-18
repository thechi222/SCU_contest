# 第三方來源

程式以各專案發布的套件為依賴，不將第三方原始碼冒稱為原創。散布部署容器時保留其套件授權及 notice。

| 元件 | 來源 | 授權 |
|---|---|---|
| faster-whisper | https://github.com/SYSTRAN/faster-whisper | MIT |
| CTranslate2 | https://github.com/OpenNMT/CTranslate2 | MIT |
| Whisper small 轉換模型 | https://huggingface.co/Systran/faster-whisper-small | 模型頁 MIT 標示，原始 Whisper 來源見模型卡 |
| Real-ESRGAN 與 x2plus 權重 | https://github.com/xinntao/Real-ESRGAN | BSD-3-Clause |
| BasicSR | https://github.com/XPixelGroup/BasicSR | Apache-2.0 |
| PyTorch / torchvision | https://pytorch.org | 各套件 BSD 類授權與第三方 notices |
| NVIDIA CUDA 容器 | https://catalog.ngc.nvidia.com/orgs/nvidia/containers/cuda | NVIDIA 容器及 CUDA 條款 |
| Django | https://github.com/django/django | BSD-3-Clause |
| Django REST Framework | https://github.com/encode/django-rest-framework | BSD-3-Clause |
| WhiteNoise | https://github.com/evansd/whitenoise | MIT |
| gunicorn | https://github.com/benoitc/gunicorn | MIT |
| APScheduler | https://github.com/agronholm/apscheduler | MIT |
| httpx | https://github.com/encode/httpx | BSD-3-Clause |

`demo-assets` 圖片由團隊校準程式產生，音訊由本機離線語音合成產生。它們是軟體驗證素材，不代表真人採訪或真實試用。

GPU 環境依據：[faster-whisper 官方需求](https://github.com/SYSTRAN/faster-whisper#gpu)、[CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/)、[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)。
