"""任務類型與其固定的模型版本。Agent 的自我測試結果須與此一致。"""

PROFILES = {
    "asr": "whisper-small-v1",
    "upscale": "realesrgan-x2-v1",
}

ARTIFACT_NAMES = {
    "asr": ["transcript.txt", "subtitles.srt"],
    "upscale": ["upscaled.png"],
}
