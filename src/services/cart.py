from typing import Dict, Tuple
from ..db import StoreDB


def brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")




def cart_summary(db: StoreDB, user_id: int) -> Tuple[str, float, Dict[str,int]]:
    items = db.get_cart(user_id)
    if not items:
        return "Seu carrinho está vazio.", 0.0, {}
    lines = []
    total = 0.0
    for sku, qty in items.items():
        p = db.get_product(sku)
        if not p:
            continue
        subtotal = p.price * qty
        total += subtotal
        lines.append(f"• {p.name} (x{qty}) — {brl(subtotal)}")
    text = "\n".join(lines) + f"\n\n**Total:** {brl(total)}"
    return text, total, items