"""Minimal settings for the separately deployable QHPC Workbench."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR.parent

SECRET_KEY = os.environ.get(
    "QHPC_WORKBENCH_SECRET_KEY",
    "qhpc-development-only-secret-key",
)
DEBUG = os.environ.get("QHPC_WORKBENCH_DEBUG", "1") == "1"

configured_host = os.environ.get("QHPC_WORKBENCH_HOST", "127.0.0.1")
ALLOWED_HOSTS = sorted({configured_host, "127.0.0.1", "localhost", "testserver"})

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "qhpc_workbench",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "qhpc_workbench.urls"
WSGI_APPLICATION = "qhpc_workbench.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.csrf",
                "django.template.context_processors.request",
            ],
        },
    }
]

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

STATIC_URL = "/static/"
STATICFILES_DIRS = [SOURCE_DIR / "qhpc_ecosystem" / "workbench"]
STATIC_ROOT = BASE_DIR / "collected-static"

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
