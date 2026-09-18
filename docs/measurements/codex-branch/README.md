# codex 分支的既有量測

本目錄的 JSON 由 `codex/compute-relay-demo` 分支的實作(FastAPI 版)於 2026-09-16 產生,
記錄同一組 GPU 容器與 worker 的實跑結果與網路協定測試。

保留這些檔案是為了不遺失既有證據,但**它們不是本分支的實測結果**:
本分支改以 Django 實作平台端,派工與 API 均為重寫。本分支自己的量測請以
`scripts/benchmark.py` 產生,並存放於上一層的 `docs/measurements/`。
