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