from dataclasses import dataclass


@dataclass
class Product:
    sku: str
    name: str
    price: float
    description: str = ""
    category: str = "geral"