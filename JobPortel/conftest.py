import pytest
from django.conf import settings

def pytest_configure():
    # This runs BEFORE any apps are loaded
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    settings.AXES_ENABLED = False
    settings.AXES_CACHE = 'default'