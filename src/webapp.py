# src/webapp.py
from fastapi import FastAPI, Request, Header
from .config import WEBHOOK_VERIFY_TOKEN, DB_PATH, ORDER_LOG_CHANNEL_ID
from .db import StoreDB
from .services.cart import brl
import json

app = FastAPI()
db = StoreDB(DB_PATH)


@app.get("/")
async def root():
    return {"ok": True, "service": "discord-sales-bot"}


@app.post("/webhook/mp")
async def mp_webhook(request: Request, x_token: str | None = Header(None)):
    # validação de segurança simples via header
    if x_token != WEBHOOK_VERIFY_TOKEN:
        return {"ok": False, "error": "invalid token"}

    payload = await request.json()
    # Esperado: {"order_id": 123, "status": "approved"}
    order_id = payload.get("order_id")
    status = payload.get("status")

    if order_id and status:
        mapped = {
            "approved": "pago",
            "rejected": "pagamento_recusado",
            "pending": "aguardando_pagamento",
        }.get(status, status)

        db.update_order_status(int(order_id), mapped)

        try:
            import discord
            from .bot import bot  # instância global do discord.py

            # busca pedido no banco
            order = db.get_order(int(order_id))
            if order:
                user_id = int(order["user_id"])
                items = json.loads(order["items_json"]) or {}

                # 1) DM padrão para o cliente quando aprovado
                if mapped == "pago":
                    try:
                        user = await bot.fetch_user(user_id)
                        if user:
                            await user.send(
                                f"✅ Olá! Seu pagamento do Pedido #{order_id} foi confirmado.\n"
                                "Nosso time vai entregar o produto diretamente no seu canal de carrinho no Discord.\n"
                                "Por favor, aguarde 😊"
                            )
                    except Exception:
                        pass

                # 2) Log no canal interno
                if ORDER_LOG_CHANNEL_ID:
                    log_channel = bot.get_channel(ORDER_LOG_CHANNEL_ID)
                    if log_channel:
                        # monta lista de itens
                        lines = []
                        for sku, q in items.items():
                            row = db.get_product_row(sku)
                            if row:
                                lines.append(f"• {row['name']} (x{q})")
                        items_text = "\n".join(lines) or "(itens indisponíveis)"

                        log_embed = discord.Embed(
                            title="📦 Atualização de Pedido",
                            description=f"ID: #{order_id}"
                        )
                        log_embed.add_field(name="Cliente ID", value=str(user_id), inline=True)
                        log_embed.add_field(name="Status", value=mapped, inline=True)
                        log_embed.add_field(name="Itens", value=items_text, inline=False)
                        log_embed.add_field(name="Total", value=brl(order["total"]), inline=True)
                        if order["payment_link"]:
                            log_embed.add_field(
                                name="Pagamento",
                                value=order["payment_link"],
                                inline=False,
                            )
                        try:
                            await log_channel.send(embed=log_embed)
                        except Exception:
                            pass
        except Exception:
            # evita crash se o bot ainda não subiu
            pass

    return {"ok": True}