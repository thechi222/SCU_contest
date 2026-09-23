"""任務目錄與租借環境。須與後端 backend/core/profiles.py 一致(README §4.1)。

AVAILABLE_KINDS 之外的任務尚未建置容器,`prepare` 會拒絕;登記於此是為了讓機台端
與平台端的鍵值、模型版本保持同一份定義。
"""

PROFILES = {
    "asr": "whisper-small-v1",
    "upscale": "realesrgan-x2-v1",
    "render": "blender-4.2-cycles-v1",
    "animate": "blender-4.2-frames-v1",
    "dataset": "datatools-v1",
    "train": "pytorch-2.4-train-v1",
}

AVAILABLE_KINDS = ["asr", "upscale"]

# 互動式租借的映像(README §4.10);機台端啟動流程尚未實作
WORKSPACES = {
    "pytorch": "powershare/workspace-pytorch:2.4-cu124",
    "datasci": "powershare/workspace-datasci:1.0",
    "blender": "powershare/workspace-blender:4.2",
}
