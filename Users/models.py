from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, user_email, password=None, **extra_fields):
        if not user_email:
            raise ValueError("Email is required")

        email = self.normalize_email(user_email)
        user = self.model(user_email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, user_email, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        return self.create_user(user_email, password, **extra_fields)

class Users(AbstractBaseUser,PermissionsMixin):
    ROLE_CHOICES = (
        ('jobseeker', 'JobSeeker'),
        ('recruiter', 'Recruiter'),
        ('admin', 'Admin'),
    )

    user_id = models.AutoField(primary_key=True)
    user_email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'user_email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
