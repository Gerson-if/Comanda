"""
Relatórios de vendas e financeiro do lojista.

Agregações são feitas em Python (não em SQL específico de dialeto) para
manter o código portável entre SQLite (dev/test) e PostgreSQL (produção)
sem depender de funções de data específicas de cada banco — o volume de
pedidos por loja não justifica a complexidade extra de agregação nativa
no banco nesta fase.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from app.models import Order, OrderItem, OrderStatus

CANCELED = OrderStatus.CANCELED.value


def _aware_utc(dt: datetime) -> datetime:
    """
    Normaliza um datetime para timezone-aware (UTC).

    SQLite (usado em dev/test) não preserva timezone-awareness ao ler de
    volta uma coluna DateTime(timezone=True) — o valor volta "naive".
    PostgreSQL (produção) preserva normalmente. Esta função torna as
    comparações seguras nos dois ambientes.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReportService:
    def __init__(self, tenant):
        self.tenant = tenant

    def _paid_orders_query(self):
        # "Receita" considera todo pedido que não foi cancelado — mesmo
        # ainda em preparo, pois já é uma venda confirmada pelo cliente.
        return Order.query.filter(
            Order.tenant_id == self.tenant.id,
            Order.status != CANCELED,
        )

    def revenue_between(self, start: datetime, end: datetime) -> int:
        orders = self._paid_orders_query().filter(
            Order.created_at >= start, Order.created_at < end
        ).all()
        return sum(o.total_cents for o in orders)

    def summary(self) -> dict:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        all_orders = self._paid_orders_query().all()

        return {
            "revenue_today_cents": sum(
                o.total_cents for o in all_orders if _aware_utc(o.created_at) >= today_start
            ),
            "revenue_week_cents": sum(
                o.total_cents for o in all_orders if _aware_utc(o.created_at) >= week_start
            ),
            "revenue_month_cents": sum(
                o.total_cents for o in all_orders if _aware_utc(o.created_at) >= month_start
            ),
            "revenue_total_cents": sum(o.total_cents for o in all_orders),
            "orders_total": len(all_orders),
        }

    def order_count_by_status(self) -> dict:
        orders = Order.query.filter(Order.tenant_id == self.tenant.id).all()
        counts = defaultdict(int)
        for order in orders:
            counts[order.status.value] += 1
        return dict(counts)

    def daily_revenue_series(self, days: int = 14) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days - 1)
        since = since.replace(hour=0, minute=0, second=0, microsecond=0)

        orders = self._paid_orders_query().all()

        by_day = defaultdict(int)
        for order in orders:
            created = _aware_utc(order.created_at)
            if created < since:
                continue
            day_key = created.date().isoformat()
            by_day[day_key] += order.total_cents

        series = []
        for i in range(days):
            day = (since + timedelta(days=i)).date()
            key = day.isoformat()
            series.append({"date": key, "revenue_cents": by_day.get(key, 0)})
        return series

    def top_products(self, limit: int = 5) -> list[dict]:
        items = (
            OrderItem.query.join(Order)
            .filter(Order.tenant_id == self.tenant.id, Order.status != CANCELED)
            .all()
        )

        aggregated = defaultdict(lambda: {"quantity": 0, "revenue_cents": 0})
        for item in items:
            entry = aggregated[item.product_name]
            entry["quantity"] += item.quantity
            entry["revenue_cents"] += item.subtotal_cents

        ranked = sorted(aggregated.items(), key=lambda kv: kv[1]["revenue_cents"], reverse=True)
        return [
            {"name": name, "quantity": data["quantity"], "revenue_cents": data["revenue_cents"]}
            for name, data in ranked[:limit]
        ]
