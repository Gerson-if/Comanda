from app.extensions import db
from app.models import Plan
from app.repositories.plan_repository import PlanRepository
from app.utils.slugs import generate_unique_slug


class AdminPlanService:
    def __init__(self):
        self.repo = PlanRepository()

    def list_all(self):
        return self.repo.list_ordered()

    def get_or_404(self, plan_id: int) -> Plan:
        from flask import abort

        plan = self.repo.get_by_id(plan_id)
        if plan is None:
            abort(404)
        return plan

    def create(self, *, name: str, description: str, price_reais: float, billing_cycle: str,
               max_categories: int | None, max_products: int | None, max_images_per_product: int) -> Plan:
        slug = generate_unique_slug(name, self.repo.get_by_slug)
        plan = Plan(
            name=name.strip(),
            slug=slug,
            description=(description or "").strip() or None,
            price_cents=round(price_reais * 100),
            billing_cycle=billing_cycle,
            max_categories=max_categories,
            max_products=max_products,
            max_images_per_product=max_images_per_product,
        )
        db.session.add(plan)
        db.session.commit()
        return plan

    def update(self, plan: Plan, *, name: str, description: str, price_reais: float, billing_cycle: str,
               max_categories: int | None, max_products: int | None, max_images_per_product: int) -> Plan:
        if name.strip() != plan.name:
            plan.slug = generate_unique_slug(name, self.repo.get_by_slug, current_id=plan.id)
        plan.name = name.strip()
        plan.description = (description or "").strip() or None
        plan.price_cents = round(price_reais * 100)
        plan.billing_cycle = billing_cycle
        plan.max_categories = max_categories
        plan.max_products = max_products
        plan.max_images_per_product = max_images_per_product
        db.session.commit()
        return plan

    def toggle_active(self, plan: Plan) -> Plan:
        plan.is_active = not plan.is_active
        db.session.commit()
        return plan
