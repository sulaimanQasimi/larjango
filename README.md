# Larajango

Larajango is a Django starter shaped like Laravel: controllers in `app/Http/Controllers`, models in `app/Models`, routes in `routes/web.py`, an `artisan` command line, and Inertia-style pages in `resources/js/Pages`.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
./artisan migrate
./artisan serve
```

In another terminal:

```bash
npm run dev
```

Open `http://127.0.0.1:8000`.

## Commands

```bash
./artisan serve
./artisan migrate
./artisan route:list
./artisan make:controller PostController
./artisan make:model Post
./artisan inertia:page Posts/Index
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
```

Controller actions can return normal Django responses or Inertia pages:

```python
from larajango.inertia import inertia

class HomeController:
    def index(request):
        return inertia(request, "Home", {"framework": "Larajango"})
```
