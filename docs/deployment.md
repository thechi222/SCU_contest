# 部署與現場準備

## 中央主機

選一台穩定電腦，三台 GPU 節點透過自備路由器連線。中央服務也可在其中一台 GPU 電腦上。故障演示選另一台節點。

建議將正式 `data` 放在本機未同步磁碟目錄，避免 OneDrive 同步 SQLite 與大檔。設定 `RELAY_DATA_DIR` 後執行 init 建立獨立資料。開發工作目錄可以保留原位置。備份需停止中央服務後複製整個資料目錄，包含資料庫與 `files`。

假設中央主機固定為 `192.168.50.10`，依實際 IP 替換：

```powershell
.venv/Scripts/python.exe scripts/create-certs.py --host 192.168.50.10
./scripts/start.ps1 -Listen 0.0.0.0 -Hosts '192.168.50.10,localhost,127.0.0.1' -Cert data/certs/server.pem -Key data/certs/server-key.pem
```

伺服器憑證 120 天有效。分享 `ca.pem` 給三台節點與展示瀏覽器，私鑰僅留中央主機。在自己管理的展示設備上匯入此 CA 到受信任根憑證存放區，再正常開啟 HTTPS 網站。不要略過瀏覽器的安全警告。CA 只供本次受控展示，結束後移除信任。

Windows 防火牆如有提示，僅允許私人網路的 TCP 8765。不要建立路由器外網轉送或公開隧道。

## 節點

1. 安裝 NVIDIA 驅動、WSL2 / Docker Desktop 或 Linux NVIDIA Container Toolkit。
2. 先執行 `doctor`。NVML 主機監控應回報 GPU 型號與記憶體。未知欄位可為 null。
3. 執行兩種 `prepare`，保存 `.agent/profiles.json` 的測試紀錄。
4. 在自己的提供者帳號取得配對碼。使用 HTTPS 與 CA 配對。

```powershell
.venv/Scripts/python.exe -m agent.main pair --server https://192.168.50.10:8765 --ca C:/relay-certs/ca.pem --name '教室 GPU 02'
.venv/Scripts/python.exe -m agent.main run
```

每個節點持有獨立設備 token，存於 `.agent/config.json`。不要共用或傳送整個 `.agent` 給別人，其他人只需模型和容器。

## 離線套件

建置好的映像可事先匯出：

```powershell
docker save -o relay-images.tar campus-relay/asr:v1 campus-relay/upscale:v1
# 另一台電腦
docker load -i relay-images.tar
```

複製 `.agent/models` 至另一台的 `.agent/models`，保留各模型目錄的 `manifest.json`。再執行 `prepare --skip-build` 逐台 CUDA 測試，自動重建對該機有效的 `profiles.json`。不要複製他人的節點憑證或直接聲稱已通過測試。

Python 套件可提前 `pip download -r requirements.lock -d wheelhouse`。離線安裝用 `pip install --no-index --find-links wheelhouse -r requirements.lock`，再 `pip install --no-deps --no-build-isolation -e .`。需將 setuptools 也提前放入 wheelhouse 並安裝。Windows/Linux 的 wheelhouse 必須各自準備。前端使用已編譯的 `frontend/dist`。

在準備完成後切斷路由器 WAN，但保留 LAN。重新登入、上傳、下載成果，並檢查三台節點。外部 Google Fonts、CDN、雲端資料庫皆不是核心流程的必要條件。

## Docker 通訊檔錯誤

本機曾出現 `initializing Inference manager ... dockerInference ... The file cannot be accessed`。Docker 在自己的啟動階段失敗，不是平台回傳的任務錯誤。

2026-09-16 的修復：確認 Docker 失敗且停止後，將 `AppData/Local/Docker/run` 和 `AppData/Local/docker-secrets-engine` 改名保留備份，重新啟動後成功讀取 Docker 29.4.3 與 GPU。沒有執行 factory reset，沒有刪除 images、volumes 或 VHDX。此處僅記錄本機實際處理，其他機器要先確認錯誤及既有容器狀態，不應直接照抄清理操作。

類似錯誤追蹤：[Docker desktop-feedback #460](https://github.com/docker/desktop-feedback/issues/460)。

## 每次彩排前

- 三台設備插電、保持散熱、關閉自動睡眠，確認模型版本相同。
- 至少兩個使用者帳號提交，以顯示三台 GPU 同時工作。
- 先完成短音訊，再提交較長圖片批次，等 GPU 運算階段才按 OFF。
- 查看實際 GPU 記憶體下降與接力事件，不把等待模型載入當成已在推論。
- 保存匯出的工作報表、benchmark JSON、實際畫面錄影。錄影若作備援，標示錄製時間及硬體。

