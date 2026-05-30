from larajango.config import env

ALLOW_ORIGIN = env("CORS_ALLOW_ORIGIN", "*")
ALLOW_METHODS = env("CORS_ALLOW_METHODS", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
ALLOW_HEADERS = env("CORS_ALLOW_HEADERS", "Content-Type, Authorization, X-Requested-With, X-Inertia")
