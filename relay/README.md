# relay

中繼伺服器(Reverse Tunnel),負責讓機台在無公網 IP / NAT 後方的情況下,
讓使用者透過中繼伺服器連進去(§2、§6.2 #3)。

實作方式待定(`frp` 或自製 SSH reverse tunnel),由機台代理 / 容器負責人主導。
