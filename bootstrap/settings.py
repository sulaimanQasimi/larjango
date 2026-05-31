from pathlib import Path

from larajango.config import env, load_env

BASE_DIR = Path(__file__).resolve().parent.parent
load_env(BASE_DIR / ".env")

from config import session

SECRET_KEY = env("APP_KEY", "larajango-dev-secret-key")
DEBUG = env("APP_DEBUG", True)
ALLOWED_HOSTS = [host for host in str(env("APP_HOSTS", "127.0.0.1,localhost,testserver")).split(",") if host]
APP_URL = env("APP_URL", "http://localhost")

INSTALLED_APPS = [
    "django_vite",
    "app.apps.Application",
    "larajango.apps.LarajangoConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "larajango.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "larajango.middleware.RequestMiddleware",
    "larajango.middleware.MethodOverrideMiddleware",
    "django.middleware.common.CommonMiddleware",
    "larajango.csrf.PreventRequestForgery",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bootstrap.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "resources" / "views"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bootstrap.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / str(env("DB_DATABASE", "database/database.sqlite3")),
    }
}

LANGUAGE_CODE = env("APP_LOCALE", "en-us")
TIME_ZONE = env("APP_TIMEZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "public"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "app.User"

DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "dev_server_host": "127.0.0.1",
        "dev_server_port": 5173,
        "static_url_prefix": "build",
        "manifest_path": BASE_DIR / "public" / "build" / "manifest.json",
    }
}

CORS = {
    "ALLOW_ORIGIN": env("CORS_ALLOW_ORIGIN", "*"),
    "ALLOW_METHODS": env("CORS_ALLOW_METHODS", "GET, POST, PUT, PATCH, DELETE, OPTIONS"),
    "ALLOW_HEADERS": env("CORS_ALLOW_HEADERS", "Content-Type, Authorization, X-Requested-With, X-Inertia"),
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "larajango",
    }
}

SESSION_ENGINE = {
    "database": "django.contrib.sessions.backends.db",
    "cache": "django.contrib.sessions.backends.cache",
    "file": "django.contrib.sessions.backends.file",
    "cookie": "django.contrib.sessions.backends.signed_cookies",
}.get(session.DRIVER, session.DRIVER)
SESSION_COOKIE_AGE = session.LIFETIME * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = session.EXPIRE_ON_CLOSE
SESSION_COOKIE_NAME = session.COOKIE
SESSION_COOKIE_PATH = session.PATH
SESSION_COOKIE_DOMAIN = session.DOMAIN
SESSION_COOKIE_SECURE = session.SECURE
SESSION_COOKIE_HTTPONLY = session.HTTP_ONLY
SESSION_COOKIE_SAMESITE = session.SAME_SITE
