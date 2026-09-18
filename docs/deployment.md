# 部署說明

適用兩種情境:一台中央服務加數台 GPU 機台的區域網路展示,以及使用者測試期間的對外服務。

## 1. 中央服務

```bash
cp .env.example .env     # 對外服務時 DJANGO_DEBUG=0,並填入 50 字元以上的 DJANGO_SECRET_KEY
docker compose up --build
docker compose exec web python manage.py seed             # 本機示範帳號(對外測試前停用)
docker compose exec web python manage.py createsuperuser  # 管理者帳號
```

`docker compose` 會啟動四個服務:`db`(PostgreSQL)、`migrate`(執行後結束)、`web`(gunicorn)、
`scheduler`(每秒清理逾期租約)。上傳與成果檔案存於 `app_data` volume,重啟不會遺失。

本機開發則使用 SQLite 與 `runserver`,見 README §3.3。

## 2. 區域網路的 HTTPS

機台 Agent 只接受 HTTPS,或 `127.0.0.1` / `localhost` 的 HTTP。跨機台時請簽發區網憑證:

```bash
pip install -r scripts/requirements.txt
python scripts/create-certs.py --host <中央服務的區網 IP>
```

把產生的 CA 交給各機台,Agent 以 `--ca` 指定;中央服務端以反向代理(nginx、Caddy)掛上伺服器憑證。
`DJANGO_ALLOWED_HOSTS` 須包含該 IP 或網域,`DJANGO_CSRF_TRUSTED_ORIGINS` 須包含 `https://` 開頭的完整網址。

## 3. 加入一台 GPU 機台

需求:NVIDIA 驅動、Docker(Windows 使用 Docker Desktop 的 WSL2 Linux 容器,
Linux 使用 NVIDIA Container Toolkit)、Python 3.11–3.12。

```bash
cd agent
pip install -r requirements.txt
python -m agent.main doctor                    # 讀取 GPU、驅動與 Docker 版本
python -m agent.main prepare --kind asr        # 首次需要網路,可能下載數 GB
python -m agent.main prepare --kind upscale
```

`prepare` 會固定容器 image ID、模型 SHA-256、GPU UUID 與驅動版本,並實跑一次 CUDA 自我測試;
只有通過的任務類型才會登錄。接著於網站「我的設備」取得一次性配對碼:

```bash
python -m agent.main pair --server https://<中央服務> --name '實驗室 RTX 3090'
# 配對碼採隱藏輸入
python -m agent.main run        # 常駐;另一個終端機執行 enable 才會開始接單
python -m agent.main enable     # 本機允許接單
python -m agent.main status
python -m agent.main stop       # 中央服務失聯時仍可在本機停止
```

網站的分享開關 OFF 與本機 `stop` 都會停止目前的容器,未完成的檔案重新排隊。
多 GPU 主機請為每張卡使用不同的 `--dir` 與 `--gpu`,例如 `--dir .agent/gpu1 prepare --gpu 1`。

## 4. 對外測試(HTTPS tunnel)

依 README §3.4 設定 `DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS` 與 `DJANGO_DEBUG=0`,
使用固定網域,限制 `/admin/` 的存取,並以 `import_users` 建立受測者個人帳號。
對外開放前,先以受測帳號實際完成一次「登入 → 上傳 → 取得成果」。

## 5. 離線準備

模型、容器 image、Python 與系統套件都應提前於各機台完成 `prepare`。
`prepare` 之後的工作容器不連外,展示當天不需要網際網路,但中央服務與機台之間的區網必須可通。
