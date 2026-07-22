from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DecimalField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from app.utils.validators import not_blank, phone_number, slug_format


class StoreInfoForm(FlaskForm):
    name = StringField("Nome da loja", validators=[DataRequired(), Length(max=150), not_blank])
    whatsapp_number = StringField("WhatsApp (com DDI+DDD)", validators=[Optional(), Length(max=20), phone_number()])
    phone = StringField("Telefone (opcional)", validators=[Optional(), Length(max=20), phone_number()])
    logo = FileField("Logo da loja", validators=[FileAllowed(["png", "jpg", "jpeg", "webp"], message="Formato não suportado.")])
    submit = SubmitField("Salvar dados da loja")


class MenuSettingsForm(FlaskForm):
    slug = StringField("Endereço do cardápio", validators=[DataRequired(), Length(min=3, max=150), slug_format])
    pickup_enabled = BooleanField("Aceitar retirada no local", default=True)
    delivery_enabled = BooleanField("Aceitar entrega", default=False)
    submit = SubmitField("Salvar")


class CheckoutSettingsForm(FlaskForm):
    delivery_fee = DecimalField("Taxa de entrega (R$)", places=2, validators=[Optional(), NumberRange(min=0)])
    free_delivery_above = DecimalField("Entrega grátis acima de (R$) — opcional", places=2, validators=[Optional(), NumberRange(min=0)])
    min_order = DecimalField("Pedido mínimo (R$) — opcional", places=2, validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField("Salvar")
