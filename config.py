# 雪球舆情监控配置
# ⚠️ 请从浏览器复制你的 xq_a_token 和 u Cookie

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://xueqiu.com",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# ⚠️ 重要：从浏览器开发者工具复制
# 登录雪球后，在请求头中找到 Cookie
COOKIES = {
    "xq_a_token": "601797f192b2540dd1885fc7d1cddc7b48374a0b",
    "u": "2274226566",
}

# 股票池（你的自选股）
SYMBOLS = [
    "SH603667",  # 五洲新春
    "SH601869",  # 长飞光纤
    "SZ002112",  # 三变科技
    "SZ002361",  # 神剑股份
    "SZ002506",  # 湖南黄金
    "SZ002155",  # 湖南黄金
    "SZ002342",  # 巨力索具
    "SZ300136",  # 信维通信
    "SZ002413",  # 雷科防务
    "SH600118",  # 中国卫星
    "SZ002149",  # 西部材料
]

# 雪球API地址
BASE_URL = "https://xueqiu.com"

# Telegram配置
TELEGRAM_BOT_TOKEN = "8577720778:AAFnet0gNmJESRwhUihHPdBO4UNjFkS7Iqs"
TELEGRAM_CHAT_ID = "8338565544"

# WhatsApp配置
WHATSAPP_TARGET = "+8613382188809"

# 采集设置
REQUEST_TIMEOUT = 10
MIN_POSTS_PER_STOCK = 20
LIVENEWS_COUNT = 50

# 分析设置
LLM_MODEL = "minimax/abab6.5s-chat"  # 使用MiniMax
TEMPERATURE = 0.2

# 信号阈值
HEAT_THRESHOLD = 5.0
SENTIMENT_THRESHOLD = 3.0
LEADING_WEIGHT = 1.5
