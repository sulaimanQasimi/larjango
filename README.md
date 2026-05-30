# Larajango

Larajango is a Django starter shaped like Laravel 12: controllers in `app/Http/Controllers`, requests in `app/Http/Requests`, middleware in `app/Http/Middleware`, models in `app/Models`, route files in `routes`, config in `config`, an `artisan` command line, and Inertia-style pages in `resources/js/Pages`.

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

## Commands

```bash
./artisan serve
./artisan dev
./artisan migrate
./artisan route:list -v
./artisan route:list --path=api
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
./artisan make:request StorePostRequest
./artisan make:seeder UserSeeder
./artisan make:policy PostPolicy
./artisan make:job SendWelcomeEmail
./artisan make:migration create_posts_table
./artisan inertia:page Posts/Index
./artisan install:api
```

You can also create another project from this framework package:

```bash
python -m larajango new blog
```

## Routing

Add routes in `routes/web.py`:

```python
from app.Http.Controllers.HomeController import HomeController
from larajango.routing import router

router.get("/", HomeController.index, name="home")

with router.group(prefix="admin", name="admin.", middleware=["auth"]):
    router.get("/dashboard", HomeController.index, name="dashboard")

router.redirect("/home", "/", status=301)
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
```

API routes live in `routes/api.py` and are automatically prefixed with `/api`.

## Middleware

Register middleware aliases and groups in `bootstrap/app.py`:

```python
from larajango.routing import router

router.alias_middleware("auth", "app.Http.Middleware.Authenticate.Authenticate")
router.middleware_group("api", ())
```

Then attach them to route groups:

```python
with router.group(prefix="account", middleware=["auth"]):
    router.get("/", AccountController.index, name="account")
```

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

Define gates:

```python
from larajango.authorization import Gate

Gate.define("update-post", lambda user, post: post.user_id == user.id)
Gate.authorize("update-post", request.user, post)
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
