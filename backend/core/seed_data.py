# 本機開發用示範帳號,密碼於建立時隨機產生
SEED_USERS = [
    {"email": "demo.student@scu.edu.tw", "name": "示範學生", "role": "student"},
    {"email": "demo.staff@scu.edu.tw", "name": "示範教職員", "role": "staff"},
]

# demo-assets/ 內可直接用於試跑的素材:離線合成語音與團隊產生的校準圖片,
# 不是真人受訪或學生試用成果。
DEMO_ASSETS = {
    "asr": ["demo-assets/introduction.wav"],
    "upscale": [
        "demo-assets/calibration.png",
        "demo-assets/batch-1.png",
        "demo-assets/batch-2.png",
        "demo-assets/batch-3.png",
        "demo-assets/batch-4.png",
    ],
}
