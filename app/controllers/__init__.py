"""
Camada de Controllers — Blueprints Flask (rotas HTTP).

Controllers são "finos": recebem a request, validam via Schema, chamam o
Service correspondente e devolvem a resposta (JSON ou template renderizado).
Não contêm lógica de negócio nem queries diretas ao banco.

Blueprints previstos (próximas fases):
- auth_controller      -> /login, /logout (Super Admin + Lojista)
- admin_controller     -> painel do Super Administrador
- lojista_controller   -> painel do Lojista (produtos, categorias, pedidos)
- public_controller    -> cardápio público (/loja/<slug>) + checkout
"""
