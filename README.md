# Larajango

Larajango is a Django starter shaped like Laravel 13: controllers in `app/Http/Controllers`, requests in `app/Http/Requests`, middleware in `app/Http/Middleware`, models in `app/Models`, route files in `routes`, config in `config`, an `artisan` command line, and Inertia-style pages in `resources/js/Pages`.

Frontend assets are served with Vite through `django-vite`. In development, Django renders the Vite HMR client, React refresh preamble, and `resources/js/app.jsx` from the Vite dev server. In production, run `npm run build` so Django can read `public/build/manifest.json` and serve the compiled files from `/static/build/`.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
./artisan migrate
./artisan dev
```

Or run the servers separately:

```bash
./artisan serve
npm run dev
```

Open `http://127.0.0.1:8000`.

The Python requirements include `django-vite` and `inertia-django`; install them with `pip install -r requirements.txt`.

## Commands

```bash
./artisan serve
./artisan dev
./artisan migrate
./artisan route:list -v
./artisan route:list -vv
./artisan route:list --path=api
./artisan route:cache
./artisan route:clear
./artisan config:show app
./artisan config:clear
./artisan cache:clear
./artisan db:seed
./artisan key:generate
./artisan storage:link
./artisan make:controller PostController
./artisan make:controller PostController --resource
./artisan make:model Post -m
./artisan make:middleware EnsureUserIsAdmin
./artisan make:middleware EnsureUserHasRole --parameters role
./artisan make:middleware LogAfterResponse --terminable
./artisan make:request StorePostRequest
./artisan make:seeder UserSeeder
./artisan make:policy PostPolicy
./artisan make:job SendWelcomeEmail
./artisan make:provider AppServiceProvider
./artisan make:migration create_posts_table
./artisan inertia:page Posts/Index
./artisan install:api
```

You can also create another project from this framework package:

```bash
python -m larajango new blog
```

## Routing

Larajango tracks Laravel 13's routing API shape as closely as Django reasonably allows. Add routes in `routes/web.py`:

```python
from app.Http.Controllers.HomeController import HomeController
from larajango.routing import router

router.get("/", HomeController.index, name="home")
router.post("/profile", ProfileController.update)
router.put("/posts/{post}", PostController.update)
router.patch("/posts/{post}", PostController.update)
router.delete("/posts/{post}", PostController.destroy)
router.options("/ping", lambda request: response(status=204))
router.match(["GET", "POST"], "/submit", SubmitController.handle)
router.any("/webhook", WebhookController.handle)
```

Redirect and view routes are available:

```python
router.redirect("/home", "/", status=302)
router.permanent_redirect("/old-home", "/")
router.view("/welcome", "welcome.html", {"name": "Taylor"})
```

Route parameters support required, optional, constrained, and catch-all segments:

```python
router.get("/users/{id}", UserController.show).where_number("id")
router.get("/users/{name?}", UserController.show).where_alpha("name")
router.get("/category/{category}", CategoryController.show).where_in("category", ["movie", "song"])
router.get("/files/{path}", FileController.show).where("path", ".*")
```

You can define global constraints in `app/Providers/AppServiceProvider.py`:

```python
from larajango.support import Route

class AppServiceProvider(ServiceProvider):
    def boot(self):
        Route.pattern("id", "[0-9]+")
```

Named routes are generated with `larajango.urls.route`:

```python
from larajango.urls import route

profile = route("profile")
```

Groups support middleware, prefixes, names, domains, controller shorthand, and scoped binding flags:

```python
with router.group(prefix="admin", name="admin.", middleware=["auth"]):
    router.get("/dashboard", HomeController.index, name="dashboard")

router.middleware(["auth", "throttle:api"]).prefix("account").name("account.").group(
    lambda: router.get("/", AccountController.index, name="index")
)

router.domain("{account}.example.com").group(
    lambda: router.get("/dashboard", TenantController.dashboard, name="tenant.dashboard")
)

router.controller(PostController).prefix("posts").name("posts.").group(lambda: (
    router.get("/", "index", name="index"),
    router.post("/", "store", name="store"),
))
```

Controller actions can return normal Django responses or Inertia pages:

```python
from larajango.inertia import inertia

class HomeController:
    def index(request):
        return inertia(request, "Home", {"framework": "Larajango"})
```

Resource controllers are supported:

```python
from app.Http.Controllers.PostController import PostController
from larajango.routing import router

router.resource("posts", PostController)
router.api_resource("api/posts", PostController)
```

API routes live in `routes/api.py` and are automatically prefixed with `/api`.

Route model binding can be explicit:

```python
from app.Models.Post import Post
from larajango.support import Route

class AppServiceProvider(ServiceProvider):
    def boot(self):
        Route.model("post", Post)
        Route.bind("slug", lambda value: Post.objects.get(slug=value))
```

Route parameters can also use Python enum annotations in controller functions. Invalid enum values return 404.

Fallback routes, current-route access, route caching, and method spoofing are included:

```python
router.fallback(lambda request, path=None: response("Not found", status=404))

current = router.current(request)
name = router.current_route_name(request)
action = router.current_route_action(request)
```

```html
{% load forms %}
<form method="POST" action="/posts/1">
  {% csrf %}
  {% method "PUT" %}
</form>
```

```bash
./artisan route:list -vv
./artisan route:cache
./artisan route:clear
```

## Middleware

Register middleware aliases and groups in `bootstrap/app.py`:

```python
from larajango.foundation import Middleware
from larajango.routing import router

middleware = Middleware(router)

middleware.alias({
    "auth": "app.Http.Middleware.Authenticate.Authenticate",
    "role": "app.Http.Middleware.EnsureUserHasRole.EnsureUserHasRole",
})

middleware.group("api", ("throttle:api",))
```

Then attach them to route groups:

```python
with router.group(prefix="account", middleware=["auth"]):
    router.get("/", AccountController.index, name="account")
```

Middleware may be attached to individual routes, excluded from routes, or chained through route groups:

```python
router.get("/profile", ProfileController.show).middleware("auth")
router.get("/public", PublicController.index).without_middleware("auth")

router.middleware(["auth", "role:admin"]).prefix("admin").group(
    lambda: router.get("/", AdminController.index, name="admin")
)
```

Middleware parameters are passed after the middleware name:

```python
class EnsureUserHasRole:
    def __init__(self, next_handler, role):
        self.next_handler = next_handler
        self.role = role

    def __call__(self, request, *args, **kwargs):
        if not request.user.groups.filter(name=self.role).exists():
            return response("Forbidden", status=403)
        return self.next_handler(request, *args, **kwargs)
```

Middleware groups can be modified Laravel-style:

```python
middleware.api(append=["throttle:api"])
middleware.web(prepend=["app.Http.Middleware.BeforeRequest.BeforeRequest"])
middleware.web(replace={"old": "new"})
middleware.web(remove=["auth"])
middleware.priority(["auth", "throttle:api"])
```

Terminable middleware can define `terminate(request, response)`:

```python
class LogAfterResponse:
    def __init__(self, next_handler):
        self.next_handler = next_handler

    def __call__(self, request, *args, **kwargs):
        return self.next_handler(request, *args, **kwargs)

    def terminate(self, request, response):
        pass
```

Rate limiters follow Laravel's `Limit` builder style:

```python
from larajango.rate_limiting import Limit, RateLimiter

RateLimiter.for_("uploads", lambda request: Limit.per_minute(100).by(request.META["REMOTE_ADDR"]))

with router.group(middleware=["throttle:uploads"]):
    router.post("/upload", UploadController.store)
```

CORS `OPTIONS` responses are handled by `larajango.middleware.CorsMiddleware`; configure defaults in `config/cors.py` or `.env`.

## CSRF Protection

Larajango uses Django's CSRF engine with Laravel-style configuration and SPA conveniences, following Laravel 13's CSRF model.

Configure request forgery protection in `bootstrap/app.py`:

```python
middleware.preventRequestForgery(
    except_paths=["stripe/*", "http://example.com/foo/*"],
    origin_only=False,
    allow_same_site=False,
    xsrf_cookie=True,
)
```

The same values may be set in `.env` through `config/csrf.py`:

```env
CSRF_ORIGIN_ONLY=false
CSRF_ALLOW_SAME_SITE=false
CSRF_XSRF_COOKIE=true
CSRF_EXCEPT=stripe/*,webhook/*
```

Include a token in HTML forms:

```html
{% load forms %}
<form method="POST" action="/profile">
  {% csrf %}
  <button type="submit">Save</button>
</form>
```

Expose the token to JavaScript with a meta tag:

```html
{% load forms %}
{% csrf_meta %}
```

AJAX requests may send either header:

```text
X-CSRF-TOKEN: <token>
X-XSRF-TOKEN: <token>
```

When enabled, Larajango also sends an `XSRF-TOKEN` cookie for Axios/Angular-style same-origin clients. Modern browser `Sec-Fetch-Site: same-origin` requests are accepted before token fallback; `allow_same_site=True` also accepts `same-site`.

## Requests

Form requests provide Laravel-style validation:

```python
from app.Http.Requests.StorePostRequest import StorePostRequest
from larajango.requests import validate

class PostController:
    @validate(StorePostRequest)
    def store(request):
        data = request.validated
```

## Configuration

Copy `.env.example` to `.env` and edit values such as `APP_NAME`, `APP_DEBUG`, and `DB_DATABASE`. Read values from Python with:

```python
from larajango.config import config, env

name = config("app.name")
debug = env("APP_DEBUG", False)
```

## Framework Package Structure

Larajango keeps old imports such as `larajango.routing` and `larajango.cache` working, but the framework package is now organized around clearer Laravel-style boundaries:

```text
larajango/
  console/        Artisan-style command application
  contracts/      Protocol interfaces for routing, cache, filesystem, queue, auth, config, HTTP
  foundation/     Application container and service provider base classes
  http/           HTTP factories and adapters
  support/        Facades and concrete repositories
  templatetags/   Django template tags for routes and Vite
```

Use contracts for type hints when your application code depends on framework services:

```python
from larajango.contracts.routing import RouterContract

def register_admin_routes(router: RouterContract):
    router.get("/admin", AdminController.index, name="admin")
```

Use service providers to register application services:

```python
from larajango.foundation import ServiceProvider

class AppServiceProvider(ServiceProvider):
    def register(self):
        self.app.singleton("reports", lambda: ReportService())
```

Providers are loaded from `bootstrap/app.py`.

Facades are available from `larajango.support`:

```python
from larajango.support import Cache, Config, Queue, Route, Storage

name = Config.get("app.name")
Cache.set("key", "value", 60)
path = Storage.disk("public").put("demo.txt", "Hello")
Queue.dispatch(lambda: "done")
```

## URL And Responses

Generate URLs from route names:

```python
from larajango.urls import route

home_url = route("home")
api_url = route("api.health")
```

Return common response types:

```python
from larajango.responses import back, json, redirect_to, response, view

return json({"ok": True})
return redirect_to("home")
return back(request)
```

## Session

Flash data and retrieve old form input:

```python
from larajango.session import flash, flash_input, flashed, old

flash(request, "status", "Saved.")
message = flashed(request, "status")
```

## Storage

Use local disks similar to Laravel's storage facade:

```python
from larajango.storage import disk

disk("public").put("avatars/user.txt", "stored")
content = disk("public").get("avatars/user.txt")
```

Expose public storage with:

```bash
./artisan storage:link
```

## Authorization And Jobs

Larajango ships with a custom `app.User` model from startup. It is configured as `AUTH_USER_MODEL`, migrated in `app/migrations/0001_initial.py`, and includes convenience helpers over Django's built-in groups and permissions:

```python
from app.Models import Permission, Role, User

user = User.objects.create_user(username="taylor", password="secret")
role = Role.find_or_create("admin")
permission = Permission.find_or_create("publish_posts")

role.give_permission_to(permission)
user.assign_role("admin")
user.give_permission_to("app.view_user")

user.has_role("admin")
user.can("app.view_user")
user.can("view_user")
```

Protect routes with role or permission middleware:

```python
router.get("/admin", AdminController.index).middleware("role:admin")
router.get("/reports", ReportController.index).middleware("permission:app.view_report")
```

Define gates:

```python
from larajango.authorization import Gate

Gate.define("update-post", lambda user, post: post.user_id == user.id)
Gate.authorize("update-post", request.user, post)
```

Policies may be registered in `app/Providers/AppServiceProvider.py`:

```python
from app.Models.User import User
from app.Policies.UserPolicy import UserPolicy
from larajango.authorization import Gate

Gate.policy(User, UserPolicy)
Gate.authorize("update", request.user, another_user)
```

Dispatch synchronous jobs:

```python
from app.Jobs.SendWelcomeEmail import SendWelcomeEmail
from larajango.queue import dispatch

dispatch(SendWelcomeEmail())
```

## Pagination And Cache

```python
from larajango.cache import remember
from larajango.pagination import paginate

posts = paginate(request, Post.objects.all(), per_page=10)
stats = remember("stats", 60, lambda: calculate_stats())
```
