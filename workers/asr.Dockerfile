FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir faster-whisper==1.2.0 ctranslate2==4.6.0 numpy==1.26.4
RUN pip3 install --no-cache-dir requests==2.32.5
COPY workers/worker.py /opt/relay/worker.py
USER 1000:1000
ENTRYPOINT ["python3", "/opt/relay/worker.py", "asr"]
