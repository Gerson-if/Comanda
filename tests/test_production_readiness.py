"""
Testes de regressão para os bugs de "tela branca" e de robustez de
produção. Existem especificamente para que esses erros não voltem a
acontecer silenciosamente em uma futura edição de template.
"""

import os
import subprocess
import sys

from app import create_app


class TestNoWhiteScreenRegression:
    def test_body_tag_never_has_x_cloak(self, client):
        """x-cloak na tag <body> some a página inteira até o Alpine.js
        carregar — se o Alpine falhar/atrasar, fica tela branca pra
        sempre. Nunca deve estar na tag body."""
        for url in ["/", "/login", "/cadastro", "/recuperar-senha"]:
            resp = client.get(url)
            html = resp.get_data(as_text=True)
            body_tag = html.split("<body", 1)[1].split(">", 1)[0]
            assert "x-cloak" not in body_tag, f"x-cloak encontrado na tag <body> de {url}"

    def test_no_external_cdn_for_critical_assets(self, client):
        """Bootstrap, Alpine.js, HTMX e Chart.js precisam ser servidos
        localmente — dependência de CDN externo pra renderizar a página
        é um ponto único de falha em produção (firewall, CSP, CDN fora
        do ar)."""
        resp = client.get("/login")
        html = resp.get_data(as_text=True)
        assert "cdn.jsdelivr.net" not in html
        assert "unpkg.com" not in html

    def test_critical_vendor_assets_are_served_locally(self, client):
        for path in [
            "/static/vendor/bootstrap/css/bootstrap.min.css",
            "/static/vendor/bootstrap/js/bootstrap.bundle.min.js",
            "/static/vendor/bootstrap-icons/bootstrap-icons.min.css",
            "/static/vendor/alpinejs/alpine.min.js",
            "/static/vendor/htmx/htmx.min.js",
            "/static/vendor/chartjs/chart.umd.js",
        ]:
            resp = client.get(path)
            assert resp.status_code == 200, f"asset local ausente: {path}"
            assert len(resp.data) > 1000, f"asset local suspeito de estar vazio/corrompido: {path}"


class TestProductionSafetyChecks:
    def _run_in_subprocess(self, env_overrides: dict, unset: list[str] | None = None) -> subprocess.CompletedProcess:
        """
        Testar a validação de config de produção precisa de um processo
        Python novo: as classes de config leem variáveis de ambiente no
        momento em que a classe é definida (import), então mudar
        os.environ e recarregar o módulo no mesmo processo não reflete
        de forma confiável (o `app/__init__.py` já importou a referência
        antiga). Um subprocesso isolado evita esse problema de cache de
        import completamente.
        """
        env = {**os.environ, **env_overrides}
        for key in unset or []:
            env.pop(key, None)

        code = (
            "from app import create_app\n"
            "create_app('production')\n"
            "print('CREATED_OK')\n"
        )
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_production_requires_database_url(self):
        result = self._run_in_subprocess({"FLASK_ENV": "production"}, unset=["DATABASE_URL"])
        assert "CREATED_OK" not in result.stdout
        assert "DATABASE_URL" in result.stderr

    def test_production_requires_non_default_secret_key(self):
        result = self._run_in_subprocess(
            {"FLASK_ENV": "production", "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db"},
            unset=["SECRET_KEY"],
        )
        assert "CREATED_OK" not in result.stdout
        assert "SECRET_KEY" in result.stderr

    def test_production_boots_with_valid_config(self):
        result = self._run_in_subprocess({
            "FLASK_ENV": "production",
            "DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db",
            "SECRET_KEY": "uma-chave-de-teste-bem-aleatoria-123456",
        })
        assert "CREATED_OK" in result.stdout, result.stderr

    def test_qrcode_generated_locally_without_external_api(self, app, client, login_as):
        login_as(client, "lojista@braseiroecia.com.br", "lojista123")
        resp = client.get("/painel/configuracoes/cardapio/qrcode.png")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"
        assert len(resp.data) > 100

        resp = client.get("/painel/configuracoes/cardapio")
        assert "api.qrserver.com" not in resp.get_data(as_text=True)
