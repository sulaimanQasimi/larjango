from app.Providers.AppServiceProvider import AppServiceProvider
from larajango.foundation.providers import load_providers
from larajango.routing import router

router.alias_middleware("auth", "app.Http.Middleware.Authenticate.Authenticate")
router.middleware_group("web", ())
router.middleware_group("api", ())

load_providers([AppServiceProvider])
