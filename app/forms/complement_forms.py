from flask_wtf import FlaskForm
from wtforms import BooleanField, DecimalField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.utils.validators import not_blank


class ComplementGroupForm(FlaskForm):
    name = StringField("Nome do grupo (ex: Tamanho, Molhos)", validators=[DataRequired(), Length(max=100), not_blank])
    is_variation = BooleanField("É uma variação do produto (ex: Tamanho — muda o próprio item)")
    is_required = BooleanField("Obrigatório escolher")
    single_choice = BooleanField("Escolha única (não múltipla)")
    submit = SubmitField("Adicionar grupo")


class ComplementOptionForm(FlaskForm):
    name = StringField("Nome da opção (ex: Grande, Barbecue)", validators=[DataRequired(), Length(max=100), not_blank])
    extra_price = DecimalField("Preço adicional (R$)", places=2, default=0, validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField("Adicionar opção")
