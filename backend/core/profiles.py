"""任務目錄與互動式租借的工作環境。Agent 的自我測試結果須與本檔一致。

`status` 欄位:
  * `available` — 已有對應的 worker 容器,使用者可送出。
  * `planned`   — 介面、成果檔名與資源需求已定義,worker 容器尚未完成,暫不開放送出。

新增任務類型的步驟見 README §6.2:先在此登記,再補上 `workers/` 的容器與模型版本,
最後把 `status` 改為 `available`。任務鍵長度不得超過 10 個字元(見 §4.1 `Job.kind`)。
"""

TASKS = {
    "asr": {
        "label": "語音轉逐字稿與字幕",
        "profile": "whisper-small-v1",
        "status": "available",
        "inputs": "音訊檔(wav / mp3 / m4a)",
        "artifacts": ["transcript.txt", "subtitles.srt"],
        "min_vram_mb": 4096,
        "note": "逐字稿保留模型輸出的用字,建議自行校對後再使用。",
    },
    "upscale": {
        "label": "圖片 2 倍放大",
        "profile": "realesrgan-x2-v1",
        "status": "available",
        "inputs": "圖片檔(png / jpg),原圖不超過 2048×2048",
        "artifacts": ["upscaled.png"],
        "min_vram_mb": 4096,
        "note": "固定 2 倍放大,不提供其他倍率或臉部修復參數。",
    },
    "render": {
        "label": "3D 靜態算圖",
        "profile": "blender-4.2-cycles-v1",
        "status": "planned",
        "inputs": "Blender 場景檔(.blend,含已打包的貼圖)",
        "artifacts": ["render.png", "render-log.txt"],
        "min_vram_mb": 8192,
        "note": "以固定的 Blender 版本與 Cycles GPU 算圖,輸出單張影像。",
    },
    "animate": {
        "label": "動畫影格算圖",
        "profile": "blender-4.2-frames-v1",
        "status": "planned",
        "inputs": "Blender 場景檔(.blend)與影格範圍設定",
        "artifacts": ["frames.zip", "preview.mp4", "render-log.txt"],
        "min_vram_mb": 8192,
        "note": "逐格算圖後合成預覽影片;影格數上限由平台設定。",
    },
    "dataset": {
        "label": "資料集批次處理",
        "profile": "datatools-v1",
        "status": "planned",
        "inputs": "資料集壓縮檔(csv / parquet)",
        "artifacts": ["dataset.parquet", "summary.json", "run-log.txt"],
        "min_vram_mb": 4096,
        "note": "以固定的清理、特徵與統計流程處理,不接受自訂程式碼。",
    },
    "train": {
        "label": "機器學習訓練",
        "profile": "pytorch-2.4-train-v1",
        "status": "planned",
        "inputs": "資料集與固定格式的設定檔(train.yaml)",
        "artifacts": ["model.safetensors", "metrics.json", "train-log.txt"],
        "min_vram_mb": 12288,
        "note": "僅提供平台預先定義的模型骨架與可填寫的超參數欄位。",
    },
}

PROFILES = {kind: task["profile"] for kind, task in TASKS.items()}
ARTIFACT_NAMES = {kind: task["artifacts"] for kind, task in TASKS.items()}
AVAILABLE_KINDS = [kind for kind, task in TASKS.items() if task["status"] == "available"]


WORKSPACES = {
    "pytorch": {
        "label": "PyTorch 訓練環境",
        "image": "powershare/workspace-pytorch:2.4-cu124",
        "status": "planned",
        "entry": "jupyter",
        "min_vram_mb": 8192,
        "note": "PyTorch 2.4、CUDA 12.4 與常用套件,以 JupyterLab 進入。",
    },
    "datasci": {
        "label": "資料科學環境",
        "image": "powershare/workspace-datasci:1.0",
        "status": "planned",
        "entry": "jupyter",
        "min_vram_mb": 4096,
        "note": "pandas、scikit-learn、RAPIDS,以 JupyterLab 進入。",
    },
    "blender": {
        "label": "Blender 算圖環境",
        "image": "powershare/workspace-blender:4.2",
        "status": "planned",
        "entry": "shell",
        "min_vram_mb": 8192,
        "note": "Blender 4.2 命令列環境,以終端機進入。",
    },
}


def task_catalog() -> list[dict]:
    """供 API 與前端顯示的任務目錄;規劃中的任務一併列出,由 status 標示能否送出。"""
    return [{"kind": kind, **task} for kind, task in TASKS.items()]


def workspace_catalog() -> list[dict]:
    return [{"key": key, **workspace} for key, workspace in WORKSPACES.items()]
