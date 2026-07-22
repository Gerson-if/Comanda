"""
Ponto de entrada WSGI, usado em produção por servidores como Gunicorn:

    gunicorn "wsgi:app"
"""

import os

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))

if __name__ == "__main__":
    app.run()
