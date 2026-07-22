from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length

from app.models.category import CATEGORY_ICON_CHOICES
from app.utils.validators import not_blank


class CategoryForm(FlaskForm):
    name = StringField(
        "Nome da categoria",
        validators=[DataRequired(message="Informe o nome."), Length(max=100), not_blank],
    )
    icon = SelectField(
        "Ícone (menu lateral do cardápio)",
        choices=CATEGORY_ICON_CHOICES,
        default="other",
    )
    is_active = BooleanField("Categoria ativa (visível no cardápio)", default=True)
    submit = SubmitField("Salvar categoria")
