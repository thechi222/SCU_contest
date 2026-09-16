# relay

中繼伺服器(Reverse Tunnel),僅負責讓使用者以瀏覽器連入 NAT 後方機台上的容器。
容器服務由機台主動建立 outbound 反向隧道,使用者請求經本中繼伺服器轉發,機台無須開放任何 inbound port。

平台對機台的控制(開通、回收容器)不經過本伺服器,而是由 Agent 主動向後端領取任務(README §4.6)。
設計說明見 README §2.3,驗收條件見 §6.2 #6。

實作方式待定(`frp` 或自建 SSH reverse tunnel),由機台 Agent / 容器負責人主導。
