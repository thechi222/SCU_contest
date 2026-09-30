# 互動式語音辨識環境(README §4.10)。與 asr.Dockerfile 同一組套件版本,
# 另加 JupyterLab 與 ffmpeg,供使用者自行操作;模型權重由 agent prepare 掛載進來。
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir faster-whisper==1.2.0 ctranslate2==4.6.0 numpy==1.26.4
RUN pip3 install --no-cache-dir jupyterlab==4.2.5
COPY workers/notebooks/asr-quickstart.ipynb /opt/powershare/asr-quickstart.ipynb
WORKDIR /work
USER 1000:1000
# 連線通道由 Agent 建立;容器只監聽本機介面,token 由 Agent 產生後回報平台
ENTRYPOINT ["jupyter", "lab", "--ServerApp.ip=127.0.0.1", "--ServerApp.port=8888", \
            "--ServerApp.open_browser=False", "--ServerApp.root_dir=/work"]
