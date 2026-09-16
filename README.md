# 算力接力站

校內 GPU 任務共享平台。提供者可隨時收回設備，未完成檔案重新排隊。使用者上傳音訊或圖片，取得逐字稿、字幕或 2 倍放大結果。

這個版本包含可運行的前後端、Python Agent、兩個固定 GPU 容器、部署腳本、測試與展示材料。**實測狀態請看 [驗收表](docs/acceptance.csv)**。協定測試中的模擬節點不代表三台實機，也不列入 GPU 效能成果。

## 在這台電腦開啟

中央服務：<http://127.0.0.1:8765>。開發預覽：<http://127.0.0.1:5173>。

1. 初始登入資訊在 `data/initial-accounts.md`，不會打包或提交 Git。
2. `admin` 管理平台；`student` 與 `provider` 都是一般成員，均可提交工作與管理自己的 GPU。若已改過密碼，初始帳號檔不會跟著更新。
3. 使用 `demo-assets/introduction.wav` 或 `calibration.png`。這些是離線合成語音與原創校準圖片，不是學生訪談成果。
4. 沒有開啟共享的相容 GPU 時，工作保留在佇列。

## 安裝與啟動

需求：Python 3.11–3.12、Node.js 22.12+、NVIDIA 驅動、Docker。Windows 使用 Docker Desktop 的 WSL2 Linux 容器，Linux 使用 NVIDIA Container Toolkit。

```powershell
# 專案根目錄；Python 不在 PATH 時傳入 -Python 完整路徑
./scripts/setup.ps1 -Python python
./scripts/start.ps1
```

Linux：`bash scripts/setup.sh`，再執行 `.venv/bin/python -m relay.cli serve`。前端已編譯時可直接由中央服務提供，不需要 Vite。

開發模式分開兩個終端：

```powershell
.venv/Scripts/python.exe -m relay.cli serve
cd frontend
npm run dev -- --port 5173
```

## 加入 GPU

請在每台 GPU 電腦的專案目錄執行。首次 prepare 需要網際網路，可能下載數 GB，之後工作容器不連外。

```powershell
.venv/Scripts/python.exe -m agent.main doctor
.venv/Scripts/python.exe -m agent.main prepare --kind asr
.venv/Scripts/python.exe -m agent.main prepare --kind upscale
```

prepare 固定容器 image ID、模型內容 SHA-256、GPU UUID、驅動版本，並實跑 CUDA。只有通過該機自我測試的服務才登錄；自我測試驗證運算能力，結果品質仍需使用真實素材評估。

登入平台的提供者帳號，在「共享設備」取得一次性配對碼，再執行：

```powershell
.venv/Scripts/python.exe -m agent.main pair --server http://127.0.0.1:8765 --name '我的 RTX 3050'
# 配對碼採隱藏輸入
.venv/Scripts/python.exe -m agent.main run
```

另一個終端啟用本機接單，再在網站開啟該設備 ON：

```powershell
.venv/Scripts/python.exe -m agent.main enable
.venv/Scripts/python.exe -m agent.main status
# 中央服務失聯時仍可在本機停止
.venv/Scripts/python.exe -m agent.main stop
```

網站 OFF 與本機 stop 均停止當前容器。Ctrl+C 結束 Agent 也會收回自己的工作。多 GPU 主機：每張卡使用不同 `--dir` 與 `--gpu`，例如 `--dir .agent/gpu1 prepare --gpu 1`，後續每個命令均使用該目錄。

## 三台電腦與離線展示

完整步驟見 [部署說明](docs/deployment.md)。中央服務預設只監聽本機，區域網路使用 HTTPS。憑證、模型、容器與 Node/Python 套件都應提前準備。

**每人預設同時最多兩件工作**。三台 GPU 同時亮起需要至少兩個帳號提交工作；若量測單一批次三機吞吐量，管理者可對專用測試帳號設上限 3，並在報告中保留設定。

## 驗證與成果

```powershell
.venv/Scripts/python.exe -m pytest --junitxml=docs/test-results.xml
cd frontend
npm run build
```

- API 測試涵蓋公平派工、三節點協定、租約過期、OFF、取消、重試上限、執行識別防舊結果覆蓋、持久化恢復、權限、額度、ZIP 與指定示範資料封存。
- `scripts/benchmark.py` 使用真實平台 API，計時包含上傳、排隊、處理與成果下載。單機與三機用相同檔案、設定及模型比較。
- [實測紀錄與待辦](docs/verification.md)、[8 分鐘展示腳本](docs/demo-script.md)、[架構與安全範圍](docs/architecture.md)、[驗收表](docs/acceptance.csv)。
- [可編輯的實測版簡報](docs/presentation/算力接力站-實測版簡報.pptx)，仍保留三機實測待填欄位。
- 原始套件：`python scripts/package.py` 產生 `release/compute-relay-demo.zip`。套件不包含帳號、模型、使用者上傳內容或私鑰。

## 本版限制

- 一個 FastAPI 程序與 SQLite。不要設定多 workers，也不要讓資料庫同時由兩台主機開啟。
- 每張 GPU 一個平台工作，非跨機合併 VRAM。中斷恢復會重新執行未完成的檔案。
- 圖片最大 2048×2048、每檔 50 MB、每批 20 檔且總量 150 MB，單工作最長 30 分鐘。圖片轉 RGB，透明資訊不保留。
- 管理者能查看全平台資料，使用者只能查看自己的檔案，機主也可能接觸自己設備處理的資料。試用使用公開或經同意的素材。
- Agent 回報 CUDA、模型與硬體證據，但這不是能抵抗惡意機主偽造的遠端驗證機制。初版供受管理且信任的校內節點。
- CPU、RAM 與網路有容器限制，GPU 顯示記憶體使用以分塊和單工作控制。NVML 無法提供的數據標示未提供。
- 逐字稿保留模型輸出的用字，中文可能含簡體字，尚未整合字形轉換與人工校對。介面使用繁體中文。
- 示範重置採可還原封存，不刪檔。正式使用需要另定資料保存與清除政策。
- 三台實機、實際學生試用、完整現場錄影與正式競賽繳件需團隊完成，驗收表保留待填欄位。

模型及第三方授權見 [THIRD_PARTY.md](THIRD_PARTY.md)。

