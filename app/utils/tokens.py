"""
Tokens de recuperação de senha — stateless (sem tabela no banco).

O token embute o ID do usuário e um fragmento do hash da senha atual.
Isso faz o token invalidar automaticamente assim que a senha é trocada
(o hash muda, o fragmento embutido não bate mais), sem precisar de uma
tabela dedicada de "tokens usados". Expira sozinho depois de
`RESET_TOKEN_MAX_AGE_SECONDS` (a assinatura embute o timestamp).
"""

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

RESET_TOKEN_MAX_AGE_SECONDS = 60 * 60  # 1 hora
RESET_SALT = "password-reset"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_reset_token(user) -> str:
    payload = {"user_id": user.id, "hash_fragment": user.password_hash[-12:]}
    return _serializer().dumps(payload, salt=RESET_SALT)


def verify_reset_token(token: str):
    """Retorna o User se o token for válido e ainda corresponder à senha
    atual, ou None caso contrário (expirado, adulterado, ou senha já
    trocada desde que o token foi gerado)."""
    from app.extensions import db
    from app.models import User

    try:
        payload = _serializer().loads(token, salt=RESET_SALT, max_age=RESET_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None

    user = db.session.get(User, payload.get("user_id"))
    if user is None:
        return None
    if user.password_hash[-12:] != payload.get("hash_fragment"):
        return None
    return user
