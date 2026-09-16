# 開發用模擬資料;正式測試前改為實際參與的機台
SEED_MACHINES = [
    {
        "id": "lab-gpu-01", "name": "資訊實驗室 GPU 工作站 #1(模擬)",
        "cpu_model": "Intel i7-12700", "gpu_model": "NVIDIA RTX 3090",
        "ram_gb": 64, "gpu_vram_gb": 24, "status": "idle",
        "owner_dept": "資訊管理學系",
    },
    {
        "id": "lab-gpu-02", "name": "資訊實驗室 GPU 工作站 #2(模擬)",
        "cpu_model": "AMD Ryzen 9 5900X", "gpu_model": "NVIDIA RTX 3060",
        "ram_gb": 32, "gpu_vram_gb": 12, "status": "offline",
        "owner_dept": "資訊管理學系",
    },
    {
        "id": "team-laptop-01", "name": "專題團隊筆電 #1(模擬)",
        "cpu_model": "Intel i5-1240P", "gpu_model": None,
        "ram_gb": 16, "gpu_vram_gb": None, "status": "idle",
        "owner_dept": "專題團隊",
    },
]

# 新建的種子機台自今日起開放預約的天數
SEED_AVAILABILITY_DAYS = 90

# 本機開發用示範帳號,密碼於建立時隨機產生
SEED_USERS = [
    {"email": "demo.student@scu.edu.tw", "name": "示範學生", "role": "student"},
    {"email": "demo.staff@scu.edu.tw", "name": "示範教職員", "role": "staff"},
]
