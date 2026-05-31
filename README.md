# Larajango

Larajango is a Django starter shaped like Laravel 13: controllers in `app/Http/Controllers`, requests in `app/Http/Requests`, middleware in `app/Http/Middleware`, models in `app/Models`, route files in `routes`, config in `config`, an `artisan` command line, and Inertia-style pages in `resources/js/Pages`.

Frontend assets are served with Vite through Larajango's Laravel-style `Vite` helper. In development, Django renders the Vite HMR client, React refresh preamble, and `resources/js/app.jsx` from the Vite dev server. In production, run `npm run build` so Django can read `public/build/manifest.json` or `public/build/.vite/manifest.json` and serve the compiled files from `/static/build/`.

## Installation

Clone the repository:

```bash
git clone https://github.com/SulaimanQasimi/larjango.git
cd larjango
```

Then install dependencies and start the development server:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
./artisan migrate
./artisan dev
```

Open `http://127.0.0.1:8000`.

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
./artisan make:view greeting
./artisan make:view greeting --blade
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
router.view("/welcome", "welcome", {"name": "Taylor"})
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

## Controllers

Controllers live in `app/Http/Controllers` and may extend `larajango.controllers.Controller`:

```python
from django.http import JsonResponse
from larajango.controllers import Controller, Middleware


class UserController(Controller):
    controller_middleware = (
        Middleware("auth", only=("index", "show")),
        Middleware("throttle:api", except_=("index",)),
    )

    def index(self, request):
        return JsonResponse({"users": []})

    def show(self, request, user):
        return JsonResponse({"user": str(user)})
```

Register controller actions with tuple syntax, controller groups, or invokable controllers:

```python
router.get("/users", (UserController, "index")).named("users.index")

router.controller(UserController).prefix("users").name("users.").group(lambda: (
    router.get("/", "index", name="index"),
    router.get("/{user}", "show", name="show"),
))

router.get("/server", ProvisionServerController)
```

Generate controllers:

```bash
./artisan make:controller UserController
./artisan make:controller PhotoController --resource
./artisan make:controller PhotoController --api
./artisan make:controller PhotoController --resource --model Photo
./artisan make:controller PhotoController --resource --requests
./artisan make:controller ProvisionServer --invokable
```

Resource controllers follow Laravel's action names:

```python
router.resource("photos", PhotoController)
router.api_resource("photos", PhotoController)
router.resources({
    "photos": PhotoController,
    "posts": PostController,
})
```

Resource registrations can be customized:

```python
router.resource("photos", PhotoController).only(("index", "show"))
router.resource("photos", PhotoController).except_(("destroy",))
router.resource("photos", PhotoController).middleware("auth")
router.resource("photos", PhotoController).middleware_for(("show",), "auth")
router.resource("photos", PhotoController).without_middleware_for(("index",), "auth")
router.resource("photos", PhotoController).names({"create": "photos.build"})
router.resource("photos", PhotoController).parameters({"photos": "image"})
router.resource("photos", PhotoController).missing(lambda request: redirect_to("photos.index"))
router.resource("photos.comments", CommentController).shallow()
router.resource("photos.comments", CommentController).scoped({"comment": "slug"})
```

Singleton controllers are available for resources that have one instance:

```python
router.singleton("profile", ProfileController)
router.singleton("profile", ProfileController).creatable().destroyable()
router.api_singleton("profile", ProfileController)
```

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

Larajango attaches a Laravel-style request wrapper at `request.larajango`. You can also type-hint `larajango.http.request.Request` on controller or route actions to receive it directly:

```python
from django.http import JsonResponse
from larajango.http.request import Request

def store(request: Request):
    return JsonResponse({
        "name": request.input("user.name"),
        "admin": request.boolean("admin"),
        "page": request.integer("page", 1),
        "token": request.bearer_token(),
        "ip": request.ip(),
    })
```

Request helpers mirror Laravel's request API where they map cleanly to Django:

```python
request.path()
request.is_("admin/*")
request.route_is("admin.*")
request.url()
request.full_url()
request.full_url_with_query({"type": "phone"})
request.full_url_without_query(["type"])
request.host()
request.http_host()
request.scheme_and_http_host()
request.method()
request.is_method("POST")
request.header("X-Header-Name", "default")
request.has_header("X-Header-Name")
request.bearer_token()
request.ip()
request.ips()
request.accepts(["text/html", "application/json"])
request.prefers(["text/html", "application/json"])
request.expects_json()
request.wants_markdown()
request.accepts_markdown()
```

Input helpers support dot notation, JSON bodies, type coercion, presence checks, merging, old input, cookies, and files:

```python
request.all()
request.input("products.0.name")
request.query("name", "Helen")
request.string("name")
request.integer("per_page", 15)
request.boolean("archived")
request.array("versions")
request.date("birthday")
request.interval("timeout", "second")
request.enum("status", Status, Status.pending)
request.enums("products", Product)
request.only("username", "password")
request.except_("credit_card")
request.has(["name", "email"])
request.has_any(["name", "email"])
request.filled("name")
request.is_not_filled(["name", "email"])
request.any_filled(["name", "email"])
request.missing("name")
request.merge({"votes": 0})
request.merge_if_missing({"votes": 0})
request.flash()
request.flash_only(["username", "email"])
request.flash_except(["password"])
request.old("username")
request.cookie("name")
request.file("photo")
request.has_file("photo")
request.file("photo").store("images", "public")
request.file("photo").store_as("images", "avatar.jpg", "public")
```

Input trimming, empty-string normalization, trusted proxies, and trusted hosts are configured in `bootstrap/app.py`:

```python
middleware.trimStrings(except_=[lambda request: request.larajango.is_("admin/*")])
middleware.convertEmptyStringsToNull(except_=[lambda request: request.larajango.is_("admin/*")])
middleware.trustProxies(at="*")
middleware.trustHosts(at=[r"^larajango\.test$"], subdomains=False)
```

## Validation

Validate request input directly from the Larajango request wrapper:

```python
from larajango.http.request import Request


def store(request: Request):
    data = request.validate({
        "title": "bail|required|max:255",
        "body": ["required", "string"],
        "author.email": "nullable|email",
        "tags": "array",
        "tags.*.name": "required|string",
    })
```

For XHR or JSON requests, failed validation returns a `422` JSON response. For normal form requests, errors and old input are flashed to the session and the user is redirected back.

Manually create validators with the facade:

```python
from larajango.support import Validator
from larajango.validation import Rule

validator = Validator.make(
    {"email": "taylor@example.com"},
    {"email": ["required", "email", Rule.unique("users", "email")]},
)

if validator.fails():
    errors = validator.errors()

validated = validator.validated()
safe = validator.safe(["email"])
```

Supported rules include common Laravel rules such as `required`, `nullable`, `sometimes`, `bail`, `email`, `min`, `max`, `between`, `size`, `string`, `integer`, `numeric`, `decimal`, `boolean`, `array`, `list`, `accepted`, `declined`, `same`, `different`, `confirmed`, `in`, `not_in`, `regex`, `alpha`, `alpha_num`, `alpha_dash`, `ascii`, `lowercase`, `uppercase`, `starts_with`, `ends_with`, `url`, `ip`, `ipv4`, `ipv6`, `uuid`, `ulid`, `json`, `date`, `before`, `after`, `mimes`, `mimetypes`, `image`, `file`, `unique`, and `exists`.

Use named error bags when a page has multiple forms:

```python
request.validate_with_bag("post", {"title": "required"})
```

Form requests provide Laravel-style validation and can be used as decorators or action type hints:

```python
from app.Http.Requests.StorePostRequest import StorePostRequest
from larajango.requests import validate

class PostController:
    @validate(StorePostRequest)
    def store(request):
        data = request.validated

    def update(request: StorePostRequest, post):
        data = request.validated()
```

Form requests may define `authorize`, `prepare_for_validation`, `with_validator`, `after`, `messages`, `attributes`, and `passed_validation`. Precognition-style checks are supported with the `Precognition` request header.

Display validation errors and old input in Django or Blade templates:

```django
{% load validation %}
{% error "title" as title_error %}
{% if title_error %}<p>{{ title_error }}</p>{% endif %}
<input name="title" value="{% old 'title' %}">
```

```blade
@error('title')
    <p>{{ $message }}</p>
@enderror

<input name="title" value="{{ old('title') }}">
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
from larajango.support import Cache, Config, Cookie, Queue, Response, Route, Storage, View

name = Config.get("app.name")
Cache.set("key", "value", 60)
path = Storage.disk("public").put("demo.txt", "Hello")
Queue.dispatch(lambda: "done")
```

## Views

Views live in `resources/views` and use Django templates with Laravel-style names. Create one from the CLI:

```bash
./artisan make:view greeting
./artisan make:view admin.profile
```

Return views from routes and controllers with the helper or facade:

```python
from larajango.responses import view
from larajango.support import View

return view("greeting", {"name": "James"})
return view("greeting").with_("name", "Victoria").with_("occupation", "Astronaut")
return View.make("admin.profile", {"user": request.user})
```

Dot notation maps to nested files, so `admin.profile` resolves to `resources/views/admin/profile.html`. Packages and apps can use fallback views and existence checks:

```python
return View.first(["custom.admin", "admin.profile"], {"user": request.user})

if View.exists("admin.profile"):
    ...
```

Share data or register composers from a service provider:

```python
from larajango.foundation import ServiceProvider
from larajango.support import View


class AppServiceProvider(ServiceProvider):
    def boot(self):
        View.share("app_name", "Larajango")
        View.composer(["profile", "dashboard"], lambda view: view.with_("count", 10))
        View.creator("*", lambda view: view.with_("created_by", "creator hook"))
```

View composers run right before rendering; creators run as soon as the view instance is created. `*` may be used as a wildcard. For deployment-style validation, cache the view manifest and clear it later:

```bash
./artisan view:cache
./artisan view:clear
```

## Vite

Use the `vite` template tag from `resources/views/app.html` or any Django view:

```django
{% load vite %}
{% vite 'resources/js/app.jsx' %}
```

The tag emits the HMR client, React refresh preamble, and entrypoint script in development. After `npm run build`, it reads the Vite manifest and emits script, stylesheet, module preload, and optional prefetch tags.

Use the facade from providers or bootstrap code to match Laravel's Vite customization flow:

```python
from larajango.support import Vite

Vite.with_entrypoints(["resources/js/app.jsx", "resources/css/app.css"])
Vite.use_build_directory("build")
Vite.use_manifest_filename("manifest.json")
Vite.use_hot_file("public/hot")
Vite.use_csp_nonce("request-nonce")
Vite.use_integrity_key("integrity")
Vite.use_asset_prefetching("load")
```

Customize generated tags:

```python
Vite.use_script_tag_attributes({"data-turbo-track": "reload"})
Vite.use_style_tag_attributes(lambda href, chunk: {"data-source": chunk.get("src", href)})
```

Generate URLs or read built asset contents:

```python
logo = Vite.asset("resources/images/logo.png")
css = Vite.content("assets/app.css")
```

Blade templates can use Laravel-style Vite directives:

```blade
@viteReactRefresh
@vite(['resources/js/app.jsx'])
```

## Blade Templates

Larajango can render `.blade.php` files from `resources/views` through a Django-backed Blade compatibility layer:

```bash
./artisan make:view greeting --blade
```

```python
from larajango.responses import view
from larajango.support import Blade

return view("greeting", {"name": "Finn"})

html = Blade.render_string("Hello, {{ $name }}.", {"name": "Samantha"})
```

Supported Blade-style syntax includes escaped and raw output, escaped JavaScript braces, comments, verbatim blocks, conditionals, auth/guest checks, loops, includes, layouts, sections, stacks, CSRF and method fields:

```blade
{{-- resources/views/greeting.blade.php --}}
@extends('layouts.app')

@section('title')
    Greeting
@endsection

@section('content')
    @auth
        Hello, {{ $name }}.
    @endauth

    @foreach ($users as $user)
        <p>{{ $user.name }}</p>
    @empty
        <p>No users.</p>
    @endforeach

    <form method="POST">
        @csrf
        @method('PUT')
    </form>
@endsection
```

Layouts and stacks map to Django blocks:

```blade
{{-- resources/views/layouts/app.blade.php --}}
<title>@yield('title', 'Larajango')</title>
@stack('scripts')
<main>@yield('content')</main>
```

Register simple custom directives from a service provider:

```python
from larajango.support import Blade

Blade.directive("datetime", lambda expression: "{{ " + expression + " }}")
Blade.without_double_encoding()
```

## Session

Larajango uses Django's configured session backend with Laravel-style helpers on top. Configure the backend in `.env` or `config/session.py`:

```env
SESSION_DRIVER=database
SESSION_LIFETIME=120
SESSION_COOKIE=larajango_session
```

Read and write session data from the request wrapper, helper, or facade:

```python
from larajango.session import session
from larajango.support import Session

request.larajango.session().put("cart.items", [1, 2])
items = request.larajango.session().get("cart.items", [])

session({"status": "Saved"})
status = session("status")

Session.put("user.name", "Taylor")
name = Session.get("user.name")
```

The session store supports Laravel-style operations:

```python
store = request.larajango.session()

store.all()
store.only(["username", "email"])
store.except_(["password"])
store.exists("cart")
store.has("cart.items")
store.missing("checkout")
store.push("cart.items", product_id)
store.pull("status", "missing")
store.increment("counter")
store.decrement("counter")
store.forget(["cart.items"])
store.flush()
store.regenerate()
store.invalidate()
```

Flash data is available for the next request and then removed:

```python
store.flash("status", "Profile updated.")
store.now("warning", "Only for this response.")
store.reflash()
store.keep(["status"])

request.larajango.flash()
request.larajango.flash_only(["username", "email"])
request.larajango.flash_except(["password"])
request.larajango.old("username")
```

Responses use the same flash store:

```python
return redirect_to("/profile").with_(request, "status", "Saved.")
return back(request).with_input(request)
```

Use the session-scoped cache for data that should be isolated to one browser session:

```python
request.larajango.session().cache().put("discount", 10, 300)
discount = request.larajango.session().cache().remember("discount", 300, lambda: 10)
```

Block concurrent requests for the same session on sensitive routes:

```python
router.post("/profile", ProfileController.update).block(lock_seconds=10, wait_seconds=10)
router.post("/checkout", CheckoutController.store).middleware("session.block:10,10")
```

## URL And Responses

Generate basic URLs, append query strings, and inspect the current request URL:

```python
from larajango.urls import URL, url

posts = url("/posts/1")
filtered = url().query("/posts?sort=latest", {"search": "Laravel", "columns": ["title", "body"]})
current = URL.current()
full = URL.full()
previous = URL.previous()
previous_path = URL.previousPath()
```

Generate URLs from route names. Route parameters fill URI placeholders, and extra values become query string parameters:

```python
from larajango.urls import Uri, action, route, signed_route, temporary_signed_route

home_url = route("home")
api_url = route("api.health")
post_url = route("post.show", {"post": post, "search": "rocket"})
controller_url = action((UserController, "profile"), {"id": 1})
signed = signed_route("unsubscribe", {"user": 1})
temporary = temporary_signed_route("unsubscribe", 1800, {"user": 1})
```

Signed routes can be protected with middleware:

```python
router.get("/unsubscribe/{user}", UnsubscribeController.show, name="unsubscribe").middleware("signed")
router.get("/preview/{id}", PreviewController.show, name="preview").middleware("signed:relative")
```

Requests expose signature helpers:

```python
request.larajango.has_valid_signature()
request.larajango.has_valid_signature_while_ignoring(["page", "order"])
```

Set default route parameters, such as a locale, from middleware or a provider:

```python
from larajango.support import URL

URL.defaults({"locale": "en"})
```

Use fluent URI objects when you want chainable URL manipulation:

```python
uri = (
    Uri.of("https://example.com")
    .with_scheme("http")
    .with_host("test.com")
    .with_port(8000)
    .with_path("/users")
    .with_query({"page": 2})
    .with_fragment("section-1")
)
```

Return common response types:

```python
from larajango.responses import back, download, event_stream, file, json, redirect_to, response, stream, view

return response("Hello", 200).header("Content-Type", "text/plain")
return json({"ok": True}).with_callback(request.larajango.input("callback"))
return view("profile", {"user": request.user})
return view(request, "profile.html", {"user": request.user}, 200)
return download("/tmp/report.csv", "report.csv")
return file("/tmp/report.pdf")
return stream(lambda: (chunk for chunk in ["a", "b"]))
return event_stream(["started", "finished"])
return redirect_to("/dashboard").with_(request, "status", "Saved.")
return back(request).with_input(request)
```

Routes and controllers may also return strings, dictionaries, lists, Django models, or querysets; Larajango converts them to HTTP responses automatically.

Responses are fluent and support headers, cookies, cache headers, and JSONP:

```python
return (
    response("Cached")
    .with_headers({"X-App": "Larajango"})
    .without_header("X-Debug")
    .cookie("mode", "dark", 60)
    .without_cookie("old")
    .cache_headers("public;max_age=30;etag")
)
```

Redirect helpers support named routes, controller actions, external URLs, flash data, and old input:

```python
return redirect_to().route("login")
return redirect_to().action((UserController, "index"))
return redirect_to().away("https://example.com")
return redirect_to("/dashboard").with_(request, "status", "Profile updated!")
return back(request).with_input(request)
```

Queue cookies before a response exists:

```python
from larajango.support import Cookie

Cookie.queue("name", "value", 60)
Cookie.expire("old")
```

Use the Laravel-style cache header middleware on routes:

```python
router.middleware("cache.headers:public;max_age=30;s_maxage=300;stale_while_revalidate=600;etag").group(
    lambda: router.get("/privacy", PrivacyController.show)
)
```

Response macros let you add project-specific response builders:

```python
from larajango.responses import ResponseFactory

ResponseFactory.macro("caps", lambda self, value: self.make(value.upper()))

return response().caps("hello")
```
