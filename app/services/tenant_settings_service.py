"""
Regras de negócio para o próprio lojista editar os dados da sua loja
(diferente de AdminTenantService, que é exclusivo do Super Admin e
gerencia QUALQUER tenant — este serviço só é chamado com o tenant da
sessão atual, nunca com um tenant_id vindo de fora)."""

from app.extensions import db
from app.repositories.tenant_repository import TenantRepository
from app.utils.slugs import generate_unique_slug
from app.utils.uploads import save_tenant_logo, delete_product_image_file, InvalidImageError


class TenantSettingsError(Exception):
    pass


class TenantSettingsService:
    def __init__(self, tenant):
        self.tenant = tenant
        self.repo = TenantRepository()

    def update_store_info(self, *, name: str, whatsapp_number: str, phone: str, logo_file_storage=None):
        self.tenant.name = name.strip()
        self.tenant.whatsapp_number = (whatsapp_number or "").strip() or None
        self.tenant.phone = (phone or "").strip() or None

        if logo_file_storage and logo_file_storage.filename:
            try:
                old_logo = self.tenant.logo_path
                self.tenant.logo_path = save_tenant_logo(self.tenant.id, logo_file_storage)
            except InvalidImageError:
                raise
            else:
                if old_logo:
                    delete_product_image_file(old_logo)

        db.session.commit()
        return self.tenant

    def update_menu_settings(self, *, slug: str, pickup_enabled: bool, delivery_enabled: bool):
        if slug != self.tenant.slug:
            existing = self.repo.get_by_slug(slug)
            if existing and existing.id != self.tenant.id:
                raise TenantSettingsError("Esse endereço já está em uso por outra loja.")
            self.tenant.slug = generate_unique_slug(slug, self.repo.get_by_slug, current_id=self.tenant.id)

        if not pickup_enabled and not delivery_enabled:
            raise TenantSettingsError("Habilite ao menos uma forma de recebimento (retirada ou entrega).")

        self.tenant.pickup_enabled = pickup_enabled
        self.tenant.delivery_enabled = delivery_enabled
        db.session.commit()
        return self.tenant

    def update_checkout_settings(self, *, delivery_fee_reais, free_delivery_above_reais, min_order_reais):
        self.tenant.delivery_fee_cents = round(delivery_fee_reais * 100) if delivery_fee_reais is not None else None
        self.tenant.free_delivery_above_cents = round(free_delivery_above_reais * 100) if free_delivery_above_reais is not None else None
        self.tenant.min_order_cents = round(min_order_reais * 100) if min_order_reais is not None else None
        db.session.commit()
        return self.tenant
