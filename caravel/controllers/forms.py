from flask.ext.wtf import Form
from wtforms import StringField, SubmitField, TextAreaField, DecimalField
from wtforms import FileField, FieldList, FormField
from wtforms.validators import Email, DataRequired, ValidationError
from caravel import policy, app
from flask_wtf.csrf import CsrfProtect

class BuyerForm(Form):
    email = StringField("Email", description="UChicago email preferred",
                validators=[Email()])
    message = TextAreaField("Message")
    submit = SubmitField("Send")

class ImageEntry(Form):
    image = FileField("Image")

class SellerForm(Form):
    title = StringField("Listing Title",
                validators=[DataRequired()])
    seller = StringField("Email", description="UChicago Email Required",
                 validators=[Email()])
    price = DecimalField("Price", places=2)
    description = TextAreaField("Description", validators=[DataRequired()])
    photos = FieldList(FormField(ImageEntry), min_entries=5)
    submit = SubmitField("Post")
    
    def validate_seller(self, field):
        if not policy.is_authorized_seller(field.data or ""):
            raise ValidationError("Only @uchicago.edu addresses are allowed.")

CsrfProtect(app)
