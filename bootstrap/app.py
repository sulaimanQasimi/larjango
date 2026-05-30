from app.Providers.AppServiceProvider import AppServiceProvider
from larajango.foundation import Middleware
from larajango.foundation.providers import load_providers
from larajango.rate_limiting import Limit, RateLimiter
from larajango.routing import router

middleware = Middleware(router)
middleware.alias(
    {
        "auth": "app.Http.Middleware.Authenticate.Authenticate",
        "throttle": "larajango.rate_limiting.ThrottleRequests",
    }
)
middleware.group("web", ())
middleware.group("api", ("throttle:api",))

RateLimiter.for_("api", lambda request: Limit.per_minute(60).by(request.META.get("REMOTE_ADDR", "unknown")))

load_providers([AppServiceProvider])
