from app.Providers.AppServiceProvider import AppServiceProvider
from config import csrf
from larajango.foundation import Middleware
from larajango.foundation.providers import load_providers
from larajango.rate_limiting import Limit, RateLimiter
from larajango.routing import router

middleware = Middleware(router)
middleware.alias(
    {
        "auth": "app.Http.Middleware.Authenticate.Authenticate",
        "can": "larajango.authorization.CanMiddleware",
        "cache.headers": "larajango.middleware.SetCacheHeaders",
        "role": "app.Http.Middleware.EnsureUserHasRole.EnsureUserHasRole",
        "permission": "app.Http.Middleware.EnsureUserHasPermission.EnsureUserHasPermission",
        "signed": "larajango.urls.ValidateSignature",
        "throttle": "larajango.rate_limiting.ThrottleRequests",
    }
)
middleware.group("web", ())
middleware.group("api", ("throttle:api",))
middleware.preventRequestForgery(
    except_paths=csrf.EXCEPT,
    origin_only=csrf.ORIGIN_ONLY,
    allow_same_site=csrf.ALLOW_SAME_SITE,
    xsrf_cookie=csrf.XSRF_COOKIE,
)

RateLimiter.for_("api", lambda request: Limit.per_minute(60).by(request.META.get("REMOTE_ADDR", "unknown")))

load_providers([AppServiceProvider])
