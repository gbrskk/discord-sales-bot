import json
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List

from .models import Product

class StoreDB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._setup()

    def _setup(self):
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                category TEXT,
                delivery_url TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS carts (
                user_id TEXT PRIMARY KEY,
                items_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                items_json TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL,
                payment_link TEXT,
                external_ref TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    # Produtos
    def upsert_product(self, p: Product, delivery_url: Optional[str] = None):
        self.conn.execute(
            "REPLACE INTO products (sku,name,price,description,category,delivery_url) VALUES (?,?,?,?,?,?)",
            (p.sku, p.name, p.price, p.description, p.category, delivery_url),
        )
        self.conn.commit()


    def get_product(self, sku: str) -> Optional[Product]:
        r = self.conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
        if not r:
            return None
        return Product(sku=r["sku"], name=r["name"], price=r["price"], description=r["description"], category=r["category"])


    def get_product_row(self, sku: str):
        return self.conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()


    def list_products(self) -> List[Product]:
        rows = self.conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        return [Product(sku=r["sku"], name=r["name"], price=r["price"], description=r["description"], category=r["category"]) for r in rows]


    def set_delivery_url(self, sku: str, url: str):
        self.conn.execute("UPDATE products SET delivery_url=? WHERE sku=?", (url, sku))
        self.conn.commit()


    # Carrinho
    def get_cart(self, user_id: int) -> Dict[str, int]:
        r = self.conn.execute("SELECT items_json FROM carts WHERE user_id=?", (str(user_id),)).fetchone()
        return json.loads(r["items_json"]) if r else {}


    def save_cart(self, user_id: int, items: Dict[str, int]):
        payload = json.dumps(items)
        self.conn.execute("REPLACE INTO carts (user_id, items_json) VALUES (?,?)", (str(user_id), payload))
        self.conn.commit()


    def clear_cart(self, user_id: int):
        self.conn.execute("DELETE FROM carts WHERE user_id=?", (str(user_id),))
        self.conn.commit()


    # Pedidos
    def create_order(self, user_id: int, items: Dict[str, int], total: float, payment_link=None, external_ref=None) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id, items_json, total, status, payment_link, external_ref, created_at) VALUES (?,?,?,?,?,?,?)",
            (str(user_id), json.dumps(items), total, "pendente", payment_link, external_ref, datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid


    def update_order_status(self, order_id: int, status: str, payment_link=None):
        self.conn.execute("UPDATE orders SET status=?, payment_link=COALESCE(?, payment_link) WHERE id=?", (status, payment_link, order_id))
        self.conn.commit()


    def get_order(self, order_id: int):
        return self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()