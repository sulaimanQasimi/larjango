from larajango.routing import router

router.alias_middleware("auth", "app.Http.Middleware.Authenticate.Authenticate")
router.middleware_group("web", ())
router.middleware_group("api", ())
