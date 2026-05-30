from larajango.config import env

ORIGIN_ONLY = env("CSRF_ORIGIN_ONLY", False)
ALLOW_SAME_SITE = env("CSRF_ALLOW_SAME_SITE", False)
XSRF_COOKIE = env("CSRF_XSRF_COOKIE", True)
EXCEPT = tuple(item.strip() for item in str(env("CSRF_EXCEPT", "")).split(",") if item.strip())
