"""
Envio do e-mail de recuperação de senha.

Este projeto não tem um serviço de e-mail (SMTP/SendGrid/SES) configurado
nesta fase. Para manter o fluxo de "esqueci minha senha" funcional e
testável em desenvolvimento, o link de redefinição é registrado no log
da aplicação em vez de enviado por e-mail de verdade.

Para produção, troque o corpo desta função por uma chamada real (ex:
Flask-Mail, SendGrid, Amazon SES) — a assinatura da função já é a
integração correta, só a implementação interna muda.
"""

from flask import current_app, url_for


def send_password_reset_email(user, token: str) -> str:
    reset_url = url_for("auth.reset_password", token=token, _external=True)

    current_app.logger.info(
        "[recuperação de senha] Link para %s: %s (válido por 1 hora)", user.email, reset_url
    )

    return reset_url
