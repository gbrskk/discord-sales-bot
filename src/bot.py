import discord
from discord.ext import commands
from discord import app_commands
from .config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DB_PATH, CART_CATEGORY_ID, PRODUCT_IMAGE_8BALL_GUIDE, DELIVERY_URL_8BALL_GUIDE
from .db import StoreDB
from .models import Product
from .ui.views import ProdutoView, CartChannelManager

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

db = StoreDB(DB_PATH)

# cria produto inicial se banco estiver vazio
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
# 📣 COMANDO ANTIGO (se quiser manter por compatibilidade)
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
async def admin_add_produto(
    interaction: discord.Interaction,
    sku: str,
    nome: str,
    preco: float,
    categoria: str,
    descricao: str | None = None,
    delivery_url: str | None = None
):
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
    cur = db.conn.cursor()
    rows = cur.execute(
        "SELECT id, user_id, total, status, created_at FROM orders ORDER BY id DESC LIMIT ?",
        (limite,)
    ).fetchall()
    if not rows:
        await interaction.response.send_message("Sem pedidos ainda.", ephemeral=True)
        return
    lines = [f"#{r['id']} • user:{r['user_id']} • {r['status']} • R$ {r['total']:.2f}" for r in rows]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


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