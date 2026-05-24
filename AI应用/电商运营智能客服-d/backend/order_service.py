from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from auth.models import Order, Product

class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_orders_by_user(self, user_id: int):
        result = await self.db.execute(select(Order).where(Order.user_id == user_id))
        return result.scalars().all()

    async def get_order_by_id(self, order_id: str):
        result = await self.db.execute(select(Order).where(Order.order_id == order_id))
        return result.scalar_one_or_none()

    async def get_product_by_id(self, product_id: str):
        result = await self.db.execute(select(Product).where(Product.product_id == product_id))
        return result.scalar_one_or_none()

    async def search_products_by_keyword(self, keyword: str):
        result = await self.db.execute(
            select(Product).where(Product.product_name.ilike(f"%{keyword}%"))
        )
        return result.scalars().all()

    def format_product_card(self, product: Product) -> dict:
        return {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "supplier": product.supplier,
            "category": product.category,
            "inventory": product.inventory,
        }

    def format_order_card(self, order: Order) -> dict:
        return {
            "order_id": order.order_id,
            "product_name": order.product_name,
            "quantity": order.quantity,
            "amount": float(order.amount),
            "logistics_status": order.logistics_status,
            "order_time": order.order_time.strftime("%Y-%m-%d %H:%M"),
        }