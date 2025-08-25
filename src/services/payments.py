from typing import Optional
from ..config import MP_ACCESS_TOKEN

# Abstração simples para pagamento. Você pode plugar outros PSPs futuramente.

class PaymentGateway:
    def __init__(self):
        self.mp = None
        if MP_ACCESS_TOKEN:
            try:
                import mercadopago
                self.mp = mercadopago.SDK(MP_ACCESS_TOKEN)
            except Exception:
                self.mp = None


    def create_payment_link(self, order_id: int, title: str, description: str, amount: float, notification_url: Optional[str] = None) -> str:
        # Se Mercado Pago estiver configurado, cria preferência de pagamento
        if self.mp:
            preference_data = {
                "items": [
                    {"title": title, "description": description, "quantity": 1, "currency_id": "BRL", "unit_price": float(amount)}
                ],
                "external_reference": str(order_id),
            }
            if notification_url:
                preference_data["notification_url"] = notification_url
            pref = self.mp.preference().create(preference_data)
            # retorna init_point (web) ou sandbox_init_point
            return pref.get("response", {}).get("init_point") or pref.get("response", {}).get("sandbox_init_point") or f"https://pagamento.exemplo/ordem/{order_id}"
        # Fallback stub
        return f"https://pagamento.exemplo/ordem/{order_id}"