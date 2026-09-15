# relay

中繼伺服器(Reverse Tunnel)。校內機台位於 NAT 與防火牆後方且無公網 IP,
由機台主動建立 outbound 反向隧道,使用者請求經本中繼伺服器轉發至機台,
機台無須開放任何 inbound port。設計說明見 README §2.3,驗收條件見 §6.2 #5。

實作方式待定(`frp` 或自建 SSH reverse tunnel),由機台 Agent / 容器負責人主導。
