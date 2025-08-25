# Discord Sales Bot — Projeto Modular (VSCode)

Abaixo está o esqueleto atualizado com **imagem no embed do produto** e **logs de pedidos** enviados para um canal interno da staff. Atualizei a estrutura para incluir a variável `ORDER_LOG_CHANNEL_ID` no `.env` e lógica para postar logs.

---

## 📁 Estrutura de pastas (atualizada)
```
discord-sales-bot/
├── .env.example
├── requirements.txt
├── README.md
└── src/
    ├── main.py
    ├── bot.py
    ├── config.py
    ├── db.py
    ├── models.py
    ├── services/
    │   ├── payments.py
    │   └── cart.py
    ├── ui/
    │   └── views.py
    └── webapp.py
```

---

## 🔐 `.env.example`
```env
# Discord
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=

# Canais/Categorias
CART_CATEGORY_ID=            # ID da categoria "CARRINHOS"
ORDER_LOG_CHANNEL_ID=        # ID do canal de logs internos da staff

# Mercado Pago
MP_ACCESS_TOKEN=
WEBHOOK_VERIFY_TOKEN=

# Produtos Digitais (defaults)
DELIVERY_URL_8BALL_GUIDE=https://exemplo.com/downloads/8ball_guide_pro.pdf
PRODUCT_IMAGE_8BALL_GUIDE=https://exemplo.com/imagens/8ball_guide.png
```

---

## 🧩 `src/config.py`
```python
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
```

---

## 🖥️ `src/ui/views.py` (alterado para logs e imagem no embed)
```python
import discord
from typing import Optional
from ..db import StoreDB
from ..services.cart import cart_summary, brl
from ..config import ORDER_LOG_CHANNEL_ID

class CartChannelManager:
    def __init__(self, db: StoreDB, cart_category_id: Optional[int]):
        self.db = db
        self.cart_category_id = cart_category_id

    async def get_or_create(self, interaction: discord.Interaction) -> discord.TextChannel:
        guild = interaction.guild
        assert guild is not None, "Use dentro de um servidor"
        channel_name = f"carrinho-{interaction.user.name}".replace(" ", "-").lower()
        existing = discord.utils.get(guild.channels, name=channel_name)
        if existing:
            return existing

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        category = None
        if self.cart_category_id:
            category = discord.utils.get(guild.categories, id=self.cart_category_id)
        return await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)


class ProdutoView(discord.ui.View):
    def __init__(self, db: StoreDB, sku: str, cart_channel_mgr: CartChannelManager):
        super().__init__(timeout=None)
        self.db = db
        self.sku = sku
        self.cart_channel_mgr = cart_channel_mgr

    @discord.ui.button(label="➕ Adicionar ao Carrinho", style=discord.ButtonStyle.green)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        cart = self.db.get_cart(interaction.user.id)
        cart[self.sku] = cart.get(self.sku, 0) + 1
        self.db.save_cart(interaction.user.id, cart)

        channel = await self.cart_channel_mgr.get_or_create(interaction)
        text, total, _ = cart_summary(self.db, interaction.user.id)
        embed = discord.Embed(title="Seu Carrinho", description=text)
        embed.add_field(name="Total", value=brl(total))
        await channel.send(f"{interaction.user.mention}, seu carrinho foi atualizado:", embed=embed)
        await interaction.response.send_message("Produto adicionado! Abra seu canal de carrinho.", ephemeral=True)

    @discord.ui.button(label="🛒 Ver Carrinho", style=discord.ButtonStyle.blurple)
    async def ver(self, interaction: discord.Interaction, button: discord.ui.Button):
        text, total, _ = cart_summary(self.db, interaction.user.id)
        await interaction.response.send_message(embed=discord.Embed(title="Seu Carrinho", description=text), ephemeral=True)

    @discord.ui.button(label="💳 Checkout", style=discord.ButtonStyle.red)
    async def checkout(self, interaction: discord.Interaction, button: discord.ui.Button):
        from ..services.payments import PaymentGateway
        text, total, items = cart_summary(self.db, interaction.user.id)
        if not items:
            await interaction.response.send_message("Carrinho vazio!", ephemeral=True)
            return
        # cria pedido e link de pagamento
        order_id = self.db.create_order(interaction.user.id, items, total)
        pg = PaymentGateway()
        payment_link = pg.create_payment_link(order_id, title="Pedido Discord", description="Produtos digitais", amount=total)
        self.db.update_order_status(order_id, "aguardando_pagamento", payment_link)
        self.db.clear_cart(interaction.user.id)

        channel = await self.cart_channel_mgr.get_or_create(interaction)
        embed = discord.Embed(title=f"Pedido #{order_id}", description=text)
        embed.add_field(name="Total", value=brl(total), inline=True)
        embed.add_field(name="Pagamento", value=f"[Clique para pagar]({payment_link})", inline=False)
        await channel.send(f"{interaction.user.mention}, seu pedido foi gerado:", embed=embed)
        await interaction.response.send_message("Pedido criado! Link de pagamento enviado no seu canal de carrinho.", ephemeral=True)

        # log interno de pedido
        if ORDER_LOG_CHANNEL_ID and interaction.guild:
            log_channel = interaction.guild.get_channel(ORDER_LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(title="📝 Novo Pedido", description=f"Pedido #{order_id}")
                log_embed.add_field(name="Cliente", value=interaction.user.mention)
                log_embed.add_field(name="Total", value=brl(total))
                log_embed.add_field(name="Status", value="aguardando_pagamento")
                await log_channel.send(embed=log_embed)
```

---

## 🤖 `src/bot.py` (alterado para incluir imagem no embed de produto + **slash commands de admin**)
```python
import discord
from discord.ext import commands
from discord import app_commands
from .config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DB_PATH, CART_CATEGORY_ID, PRODUCT_IMAGE_8BALL_GUIDE
from .db import StoreDB
from .models import Product
from .ui.views import ProdutoView, CartChannelManager

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

db = StoreDB(DB_PATH)

from .config import DELIVERY_URL_8BALL_GUIDE
if not db.list_products():
    db.upsert_product(Product(
        sku="8BALL_GUIDE_PRO",
        name="8 Ball Pool – Guia Pro (PDF)",
        price=29.90,
        description="Guia avançado de estratégias: mira, break, rotação e posicionamento.",
        category="jogos"
    ), delivery_url=DELIVERY_URL_8BALL_GUIDE)

cart_channel_mgr = CartChannelManager(db, CART_CATEGORY_ID)

@bot.event
async def on_ready():
    try:
        if DISCORD_GUILD_ID:
            await bot.tree.sync(guild=discord.Object(id=int(DISCORD_GUILD_ID)))
        else:
            await bot.tree.sync()
    except Exception as e:
        print("Sync error:", e)
    print(f"✅ Logado como {bot.user} (ID: {bot.user.id})")

# ----------------------------
# 📣 POSTAR PRODUTO NA VITRINE
# ----------------------------
@bot.command(name="postar_produto")
@commands.has_permissions(administrator=True)
async def postar_produto(ctx: commands.Context, sku: str):
    row = db.get_product_row(sku)
    if not row:
        await ctx.send("SKU não encontrado.")
        return
    embed = discord.Embed(title=row["name"], description=row["description"] or "")
    embed.add_field(name="Preço", value=f"R$ {row['price']:.2f}".replace('.', ','))
    if sku == "8BALL_GUIDE_PRO" and PRODUCT_IMAGE_8BALL_GUIDE:
        embed.set_thumbnail(url=PRODUCT_IMAGE_8BALL_GUIDE)
    view = ProdutoView(db, sku, cart_channel_mgr)
    await ctx.send(embed=embed, view=view)

# ----------------------------
# 🔧 SLASH COMMANDS (ADMIN)
# ----------------------------

def admin_only():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

@bot.tree.command(name="admin_add_produto", description="(Admin) Cadastrar/atualizar produto digital")
@admin_only()
@app_commands.describe(
    sku="SKU único (ex: 8BALL_GUIDE_PRO)",
    nome="Nome do produto",
    preco="Preço em BRL (use ponto)",
    categoria="Categoria (ex: jogos, ebooks, cursos)",
    descricao="Descrição (opcional)",
    delivery_url="Link de entrega/download (opcional)"
)
async def admin_add_produto(interaction: discord.Interaction, sku: str, nome: str, preco: float, categoria: str, descricao: str | None = None, delivery_url: str | None = None):
    p = Product(sku=sku, name=nome, price=preco, description=descricao or "", category=categoria)
    db.upsert_product(p, delivery_url=delivery_url)
    await interaction.response.send_message(f"✅ Produto salvo: **{p.name}** `{p.sku}` — R$ {preco:.2f}", ephemeral=True)

@bot.tree.command(name="admin_set_delivery", description="(Admin) Definir/alterar delivery_url de um SKU")
@admin_only()
async def admin_set_delivery(interaction: discord.Interaction, sku: str, delivery_url: str):
    row = db.get_product_row(sku)
    if not row:
        await interaction.response.send_message("SKU não encontrado.", ephemeral=True)
        return
    db.set_delivery_url(sku, delivery_url)
    await interaction.response.send_message("✅ delivery_url atualizado.", ephemeral=True)

@bot.tree.command(name="admin_listar_pedidos", description="(Admin) Lista últimos pedidos")
@admin_only()
async def admin_listar_pedidos(interaction: discord.Interaction, limite: int = 10):
    # leitura simples direto no DB; para algo mais robusto, crie método específico
    cur = db.conn.cursor()
    rows = cur.execute("SELECT id, user_id, total, status, created_at FROM orders ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    if not rows:
        await interaction.response.send_message("Sem pedidos ainda.", ephemeral=True)
        return
    lines = [f"#{r['id']} • user:{r['user_id']} • {r['status']} • R$ {r['total']:.2f}" for r in rows]
    await interaction.response.send_message("
".join(lines), ephemeral=True)

@bot.tree.command(name="admin_postar_produto", description="(Admin) Postar um produto na vitrine (canal atual)")
@admin_only()
async def admin_postar_produto(interaction: discord.Interaction, sku: str):
    row = db.get_product_row(sku)
    if not row:
        await interaction.response.send_message("SKU não encontrado.", ephemeral=True)
        return
    embed = discord.Embed(title=row["name"], description=row["description"] or "")
    embed.add_field(name="Preço", value=f"R$ {row['price']:.2f}".replace('.', ','))
    if sku == "8BALL_GUIDE_PRO" and PRODUCT_IMAGE_8BALL_GUIDE:
        embed.set_thumbnail(url=PRODUCT_IMAGE_8BALL_GUIDE)
    view = ProdutoView(db, sku, cart_channel_mgr)
    await interaction.response.send_message("✅ Produto postado!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=view)


def run_bot():
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("Defina DISCORD_BOT_TOKEN no .env")
    bot.run(DISCORD_BOT_TOKEN)
```python
import discord
from discord.ext import commands
from .config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DB_PATH, CART_CATEGORY_ID, PRODUCT_IMAGE_8BALL_GUIDE
from .db import StoreDB
from .models import Product
from .ui.views import ProdutoView, CartChannelManager

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

db = StoreDB(DB_PATH)

from .config import DELIVERY_URL_8BALL_GUIDE
if not db.list_products():
    db.upsert_product(Product(
        sku="8BALL_GUIDE_PRO",
        name="8 Ball Pool – Guia Pro (PDF)",
        price=29.90,
        description="Guia avançado de estratégias: mira, break, rotação e posicionamento.",
        category="jogos"
    ), delivery_url=DELIVERY_URL_8BALL_GUIDE)

cart_channel_mgr = CartChannelManager(db, CART_CATEGORY_ID)

@bot.event
async def on_ready():
    try:
        if DISCORD_GUILD_ID:
            await bot.tree.sync(guild=discord.Object(id=int(DISCORD_GUILD_ID)))
        else:
            await bot.tree.sync()
    except Exception as e:
        print("Sync error:", e)
    print(f"✅ Logado como {bot.user} (ID: {bot.user.id})")

@bot.command(name="postar_produto")
@commands.has_permissions(administrator=True)
async def postar_produto(ctx: commands.Context, sku: str):
    row = db.get_product_row(sku)
    if not row:
        await ctx.send("SKU não encontrado.")
        return
    embed = discord.Embed(title=row["name"], description=row["description"] or "")
    embed.add_field(name="Preço", value=f"R$ {row['price']:.2f}".replace('.', ','))
    # adiciona imagem se SKU for 8BALL_GUIDE_PRO
    if sku == "8BALL_GUIDE_PRO" and PRODUCT_IMAGE_8BALL_GUIDE:
        embed.set_thumbnail(url=PRODUCT_IMAGE_8BALL_GUIDE)
    view = ProdutoView(db, sku, cart_channel_mgr)
    await ctx.send(embed=embed, view=view)


def run_bot():
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("Defina DISCORD_BOT_TOKEN no .env")
    bot.run(DISCORD_BOT_TOKEN)
```

