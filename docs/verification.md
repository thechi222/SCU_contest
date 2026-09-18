# 實測紀錄與待辦

狀態總表見 [acceptance.csv](acceptance.csv)。本文件記錄各項證據的取得方式,以及尚未完成的部分。

## 已驗證(自動化測試)

```bash
pip install -r tests/requirements.txt
pytest
```

涵蓋:同一節點同時只接一件工作、公平派工輪替、租約逾時重排、機主收回、重試上限、
逾時結果拒絕、取消與重送、上傳限制與每日額度、他人資料存取、錯誤格式與 JSON 404/500、
配對碼一次性、未通過自我測試的 GPU 不得登錄、撤銷設備後 token 失效。

這些測試使用暫存資料庫與模擬節點。**它們驗證協定,不能證明 CUDA 執行、三台實機或效能提升。**

## 待辦(需要實機)

1. **Docker 映像與 compose**:`docker compose up --build` 尚未在本分支執行過。
2. **真實 Agent 連線**:`agent/` 由 `codex/compute-relay-demo` 分支移植,API 路徑與欄位已對齊本分支
   (pair、heartbeat、claim、attempts/{id}/input、complete、fail),但尚未以真實 Agent 實跑。
   首次接線請先確認心跳回傳的 `stop`、`lease_seconds`、`sharing`、`within_schedule` 四個欄位。
3. **GPU 容器**:在具 NVIDIA GPU 的機台執行 `agent prepare`,記錄 image ID、模型 SHA-256、
   GPU UUID、驅動版本與自我測試輸出。
4. **三機同時派工**:至少兩個帳號同時送件才會同時點亮三台(每人同時上限預設 2)。
   若要量測單一批次的三機吞吐量,可由管理者將測試帳號的同時上限調為 3,並在報告中保留該設定。
5. **效能比較**:`python scripts/benchmark.py --kind asr --email <帳號> --password <密碼> <檔案...>`,
   單機與三機使用相同檔案、設定與模型,產生的 JSON 存於 `docs/measurements/`。
   計時為壁鐘時間,包含上傳、排隊、處理與下載,不等於純 GPU 時間。
6. **成果品質**:`demo-assets/` 是離線合成語音與團隊產生的校準圖片,只能驗證流程,
   不代表辨識或放大品質;品質評估需使用真實素材並人工檢視。

## 已知限制

- 逐字稿保留模型輸出的用字,中文可能出現簡體字,尚未整合字形轉換與人工校對。
- 每張 GPU 同時一件工作,不跨機合併顯示記憶體;中斷後重新執行整個檔案,不做斷點續跑。
- 管理者可查看全平台資料,機主可能接觸自己設備處理的檔案。試用請使用公開或已取得同意的素材。
- 單一 Django 服務;PostgreSQL 由 Docker Compose 提供,資料庫不對外發布連接埠。
