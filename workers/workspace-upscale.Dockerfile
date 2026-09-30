# 互動式影像放大環境(README §4.10)。與 upscale.Dockerfile 同一組套件版本,
# 另加 JupyterLab,供使用者自行選倍率與批次處理方式;權重由 agent prepare 掛載進來。
FROM nvidia/cuda:12.3.2-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
RUN pip3 install --no-cache-dir numpy==1.26.4 pillow==11.3.0 opencv-python-headless==4.11.0.86 basicsr==1.4.2 realesrgan==0.3.0
RUN pip3 install --no-cache-dir jupyterlab==4.2.5
COPY workers/notebooks/upscale-quickstart.ipynb /opt/powershare/upscale-quickstart.ipynb
WORKDIR /work
USER 1000:1000
ENTRYPOINT ["jupyter", "lab", "--ServerApp.ip=127.0.0.1", "--ServerApp.port=8888", \
            "--ServerApp.open_browser=False", "--ServerApp.root_dir=/work"]
