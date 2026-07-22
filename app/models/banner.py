from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantScopedMixin, TimestampMixin


class Banner(db.Model, TenantScopedMixin, TimestampMixin):
    """Banner promocional exibido no carrossel do cardápio público."""

    __tablename__ = "banners"

    id = Column(Integer, primary_key=True)
    title = Column(String(120), nullable=False)
    subtitle = Column(String(200), nullable=True)
    link_url = Column(String(255), nullable=True)
    image_path = Column(String(255), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    tenant = relationship("Tenant", back_populates="banners")

    def __repr__(self):
        return f"<Banner {self.title}>"
