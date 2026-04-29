from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

phone_validator = RegexValidator(
    regex=r'^\d{10}$',
    message="Enter a valid 10-digit phone number"
)
