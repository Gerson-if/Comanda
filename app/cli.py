"""
Comandos de linha de comando customizados.

Uso:
    flask seed-db      -> cria super admin + plano + loja demo (idempotente)
    flask create-admin -> cria (ou atualiza) um super admin específico
"""

import click
from flask import Flask

from app.extensions import db
from app.models import Plan, BillingCycle, Tenant, TenantStatus, User, UserRole


def register_cli(app: Flask) -> None:
    app.cli.add_command(seed_db)
    app.cli.add_command(create_admin)


@click.command("seed-db")
def seed_db():
    """Popula o banco com dados mínimos para começar a testar localmente."""

    # --- Super Admin ---
    admin = User.query.filter_by(email="admin@cardapio.saas").first()
    if not admin:
        admin = User(
            name="Super Administrador",
            email="admin@cardapio.saas",
            role=UserRole.SUPER_ADMIN,
            tenant_id=None,
        )
        admin.set_password("admin123")
        db.session.add(admin)
        click.echo("✔ Super admin criado: admin@cardapio.saas / admin123")
    else:
        click.echo("• Super admin já existia, pulando.")

    # --- Plano padrão ---
    plan = Plan.query.filter_by(slug="basico").first()
    if not plan:
        plan = Plan(
            name="Básico",
            slug="basico",
            description="Plano inicial para lojistas.",
            price_cents=4990,
            billing_cycle=BillingCycle.MONTHLY,
            max_products=50,
            max_categories=10,
        )
        db.session.add(plan)
        db.session.flush()
        click.echo("✔ Plano 'Básico' criado.")
    else:
        click.echo("• Plano 'Básico' já existia, pulando.")

    # --- Loja demo (migrando o cardápio original: Braseiro & Cia) ---
    tenant = Tenant.query.filter_by(slug="braseiro-cia").first()
    if not tenant:
        tenant = Tenant(
            name="Braseiro & Cia",
            slug="braseiro-cia",
            email="contato@braseiroecia.com.br",
            whatsapp_number="5567999999999",
            plan_id=plan.id,
            status=TenantStatus.ACTIVE,
            delivery_enabled=True,
            pickup_enabled=True,
        )
        db.session.add(tenant)
        db.session.flush()
        click.echo("✔ Loja demo 'Braseiro & Cia' criada.")

        owner = User(
            name="Dono do Braseiro & Cia",
            email="lojista@braseiroecia.com.br",
            role=UserRole.OWNER,
            tenant_id=tenant.id,
        )
        owner.set_password("lojista123")
        db.session.add(owner)
        click.echo("✔ Usuário lojista criado: lojista@braseiroecia.com.br / lojista123")
    else:
        click.echo("• Loja demo já existia, pulando.")

    db.session.commit()
    click.echo("Seed concluído.")


@click.command("create-admin")
@click.option("--name", prompt=True)
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
def create_admin(name, email, password):
    """Cria (ou reseta a senha de) um super administrador específico."""

    admin = User.query.filter_by(email=email).first()
    if admin:
        admin.set_password(password)
        admin.role = UserRole.SUPER_ADMIN
        admin.tenant_id = None
        click.echo(f"✔ Senha atualizada para o super admin existente: {email}")
    else:
        admin = User(name=name, email=email, role=UserRole.SUPER_ADMIN, tenant_id=None)
        admin.set_password(password)
        db.session.add(admin)
        click.echo(f"✔ Super admin criado: {email}")

    db.session.commit()
