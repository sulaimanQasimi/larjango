from larajango.config import env

DRIVER = env("SESSION_DRIVER", "database")
LIFETIME = int(env("SESSION_LIFETIME", 120))
EXPIRE_ON_CLOSE = env("SESSION_EXPIRE_ON_CLOSE", False)
COOKIE = env("SESSION_COOKIE", "larajango_session")
PATH = env("SESSION_PATH", "/")
DOMAIN = env("SESSION_DOMAIN", None)
SECURE = env("SESSION_SECURE_COOKIE", False)
HTTP_ONLY = env("SESSION_HTTP_ONLY", True)
SAME_SITE = env("SESSION_SAME_SITE", "Lax")
