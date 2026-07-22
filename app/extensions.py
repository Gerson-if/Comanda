"""
Instâncias únicas das extensões Flask.

Ficam centralizadas aqui (sem vínculo a nenhuma app específica) para
evitar imports circulares: models, services e controllers importam
`db`, `bcrypt`, etc. daqui, e o `create_app()` em __init__.py faz o
`.init_app(app)` de cada uma.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from flask_marshmallow import Marshmallow
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
ma = Marshmallow()
limiter = Limiter(key_func=get_remote_address)

# Configurações do Flask-Login
login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"
