from larajango.config import env

NAME = env("APP_NAME", "Larajango")
ENV = env("APP_ENV", "local")
DEBUG = env("APP_DEBUG", True)
URL = env("APP_URL", "http://127.0.0.1:8000")
TIMEZONE = env("APP_TIMEZONE", "UTC")
LOCALE = env("APP_LOCALE", "en-us")
