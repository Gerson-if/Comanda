from app.extensions import db
from app.models import Category
from app.repositories.category_repository import CategoryRepository
from app.utils.slugs import generate_unique_slug


class CategoryLimitReachedError(Exception):
    pass


class CategoryService:
    def __init__(self, tenant):
        self.tenant = tenant
        self.repo = CategoryRepository(tenant.id)

    def list_all(self):
        return self.repo.list_ordered()

    def get_or_404(self, category_id: int) -> Category:
        from flask import abort

        category = self.repo.get_by_id(category_id)
        if category is None:
            abort(404)
        return category

    def create(self, name: str, is_active: bool, icon: str = "other") -> Category:
        plan = self.tenant.plan
        if plan and plan.max_categories is not None and self.repo.count() >= plan.max_categories:
            raise CategoryLimitReachedError(
                f"Seu plano permite no máximo {plan.max_categories} categorias. "
                "Fale com o suporte para ampliar seu plano."
            )

        slug = generate_unique_slug(name, self.repo.get_by_slug)
        max_order = db.session.query(db.func.max(Category.display_order)).filter(
            Category.tenant_id == self.tenant.id
        ).scalar() or 0

        category = Category(
            tenant_id=self.tenant.id,
            name=name.strip(),
            slug=slug,
            icon=icon or "other",
            is_active=is_active,
            display_order=max_order + 1,
        )
        db.session.add(category)
        db.session.commit()
        return category

    def update(self, category: Category, name: str, is_active: bool, icon: str = "other") -> Category:
        if name.strip() != category.name:
            category.slug = generate_unique_slug(name, self.repo.get_by_slug, current_id=category.id)
        category.name = name.strip()
        category.icon = icon or "other"
        category.is_active = is_active
        db.session.commit()
        return category

    def toggle_active(self, category: Category) -> Category:
        category.is_active = not category.is_active
        db.session.commit()
        return category

    def delete(self, category: Category) -> None:
        # Produtos da categoria não são excluídos: category_id vira NULL
        # (ondelete="SET NULL" no model), o produto fica "sem categoria"
        # em vez de sumir do cardápio.
        db.session.delete(category)
        db.session.commit()
