from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


phone_validator = RegexValidator(
    regex=r'^\d{10}$',
    message="Enter a valid 10-digit phone number"
)


def validate_skill_name(value):
    if len(value.strip()) < 2:
        raise ValidationError("Skill name must be at least 2 characters")