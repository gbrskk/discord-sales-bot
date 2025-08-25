import os
from dotenv import load_dotenv


load_dotenv()


DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DB_PATH = os.getenv("DB_PATH", "store.db")
CURRENCY = "BRL"


# Categoria e canal de logs
CART_CATEGORY_ID = int(os.getenv("CART_CATEGORY_ID", "0")) or None
ORDER_LOG_CHANNEL_ID = int(os.getenv("ORDER_LOG_CHANNEL_ID", "0")) or None


# Mercado Pago
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "changeme")


# Produtos default
DELIVERY_URL_8BALL_GUIDE = os.getenv(
    "DELIVERY_URL_8BALL_GUIDE", "https://exemplo.com/downloads/8ball_guide_pro.pdf"
)
PRODUCT_IMAGE_8BALL_GUIDE = os.getenv(
    "PRODUCT_IMAGE_8BALL_GUIDE", "https://exemplo.com/imagens/8ball_guide.png"
)