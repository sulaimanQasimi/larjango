from __future__ import annotations

import argparse
from datetime import datetime
from importlib import import_module
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()


def main(argv: list[str] | None = None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "new":
        return new_project(argv[1:])

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bootstrap.settings")

    if not argv or argv[0] in {"-h", "--help", "help"}:
        return help_text()

    command = argv[0]
    args = argv[1:]

    if command == "serve":
        return django(["runserver", *args])
    if command == "migrate":
        return django(["migrate", *args])
    if command == "makemigrations":
        return django(["makemigrations", *args])
    if command == "shell":
        return django(["shell", *args])
    if command == "test":
        return django(["test", *args])
    if command == "dev":
        return dev(args)
    if command == "route:list":
        return route_list(args)
    if command == "config:show":
        return config_show(args)
    if command == "db:seed":
        return db_seed(args)
    if command == "install:api":
        return install_api()
    if command == "make:controller":
        return make_controller(args)
    if command == "make:model":
        return make_model(args)
    if command == "make:middleware":
        return make_middleware(args)
    if command == "make:request":
        return make_request(args)
    if command == "make:seeder":
        return make_seeder(args)
    if command == "make:migration":
        return make_migration(args)
    if command == "inertia:page":
        return make_page(args)

    return django(argv)


def django(args: list[str]):
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", *args])


def help_text():
    print(
        """Larajango commands

Usage:
  ./artisan serve
  ./artisan migrate
  ./artisan dev
  ./artisan route:list
  ./artisan config:show app
  ./artisan db:seed
  ./artisan make:controller NameController
  ./artisan make:model Name
  ./artisan make:middleware EnsureUserIsAdmin
  ./artisan make:request StorePostRequest
  ./artisan make:seeder UserSeeder
  ./artisan make:migration create_posts_table
  ./artisan inertia:page Dashboard/Index
  python -m larajango new project_name
"""
    )


def dev(args: list[str]):
    django_proc = subprocess.Popen([sys.executable, "manage.py", "runserver", *(args or [])])
    npm_proc = subprocess.Popen(["npm", "run", "dev"])
    try:
        django_proc.wait()
    finally:
        npm_proc.terminate()


def route_list(args: list[str]):
    parser = argparse.ArgumentParser(prog="./artisan route:list")
    parser.add_argument("--path", default="")
    parser.add_argument("-v", "--verbose", action="store_true")
    parsed = parser.parse_args(args)

    import routes.web  # noqa: F401
    try:
        import routes.api  # noqa: F401
    except ModuleNotFoundError:
        pass
    from larajango.routing import router

    middleware_header = " MIDDLEWARE" if parsed.verbose else ""
    print(f"{'METHOD':<18} {'URI':<30} {'NAME':<24} ACTION{middleware_header}")
    print("-" * (105 if parsed.verbose else 92))
    for route in router.routes:
        if parsed.path and not route.uri.strip("/").startswith(parsed.path.strip("/")):
            continue
        action = f"{route.action.__module__}.{route.action.__qualname__}"
        methods = "|".join(route.methods)
        middleware = ", ".join(str(item) for item in route.middleware)
        suffix = f" {middleware}" if parsed.verbose else ""
        print(f"{methods:<18} {route.uri:<30} {(route.name or ''):<24} {action}{suffix}")


def config_show(args: list[str]):
    namespace = require_name(args, "config namespace")
    module = import_module(f"config.{namespace}")
    for key in sorted(name for name in dir(module) if name.isupper()):
        print(f"{namespace}.{key.lower()}={getattr(module, key)}")


def db_seed(args: list[str]):
    class_name = args[0] if args else "DatabaseSeeder"
    module = import_module(f"database.seeders.{class_name}")
    seeder = getattr(module, class_name)()
    seeder.run()
    print(f"Seeded with {class_name}.")


def install_api():
    path = ROOT / "routes" / "api.py"
    if path.exists():
        print("routes/api.py already exists.")
        return
    create_file(
        path,
        '''from django.http import JsonResponse

from larajango.routing import router


def health(request):
    return JsonResponse({"ok": True})


with router.group(prefix="api", name="api.", middleware=["api"]):
    router.get("/health", health, name="health")
''',
    )


def make_controller(args: list[str]):
    parser = argparse.ArgumentParser(prog="./artisan make:controller")
    parser.add_argument("name")
    parser.add_argument("--resource", action="store_true")
    parsed = parser.parse_args(args)
    name = parsed.name
    class_name = name if name.endswith("Controller") else f"{name}Controller"
    path = ROOT / "app" / "Http" / "Controllers" / f"{class_name}.py"
    if parsed.resource:
        return create_file(path, resource_controller_stub(class_name))
    create_file(
        path,
        f'''from larajango.inertia import inertia


class {class_name}:
    def index(request):
        return inertia(request, "{class_name.removesuffix("Controller")}/Index", {{}})
''',
    )


def make_model(args: list[str]):
    parser = argparse.ArgumentParser(prog="./artisan make:model")
    parser.add_argument("name")
    parser.add_argument("-m", "--migration", action="store_true")
    parsed = parser.parse_args(args)
    name = parsed.name
    path = ROOT / "app" / "Models" / f"{name}.py"
    create_file(
        path,
        f'''from django.db import models


class {name}(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "app"
''',
    )
    if parsed.migration:
        make_migration([f"create_{name.lower()}s_table"])


def make_middleware(args: list[str]):
    name = require_name(args, "middleware name")
    path = ROOT / "app" / "Http" / "Middleware" / f"{name}.py"
    create_file(
        path,
        f'''class {name}:
    def __init__(self, next_handler):
        self.next_handler = next_handler

    def __call__(self, request, *args, **kwargs):
        return self.next_handler(request, *args, **kwargs)
''',
    )


def make_request(args: list[str]):
    name = require_name(args, "request name")
    path = ROOT / "app" / "Http" / "Requests" / f"{name}.py"
    create_file(
        path,
        f'''from larajango.requests import FormRequest


class {name}(FormRequest):
    rules = {{
        "name": "required|max:255",
    }}
''',
    )


def make_seeder(args: list[str]):
    name = require_name(args, "seeder name")
    class_name = name if name.endswith("Seeder") else f"{name}Seeder"
    path = ROOT / "database" / "seeders" / f"{class_name}.py"
    create_file(
        path,
        f'''class {class_name}:
    def run(self):
        pass
''',
    )


def make_migration(args: list[str]):
    name = require_name(args, "migration name")
    timestamp = datetime.utcnow().strftime("%Y_%m_%d_%H%M%S")
    path = ROOT / "database" / "migrations" / f"{timestamp}_{name}.py"
    create_file(
        path,
        f'''class Migration:
    name = "{name}"

    def up(self):
        pass

    def down(self):
        pass
''',
    )


def make_page(args: list[str]):
    name = require_name(args, "page name").strip("/")
    path = ROOT / "resources" / "js" / "Pages" / f"{name}.jsx"
    component_name = "".join(part.title().replace("_", "") for part in Path(name).parts)
    create_file(
        path,
        f'''export default function {component_name}({{ auth }}) {{
  return (
    <main className="page">
      <h1>{name}</h1>
      <p>Build this page in <code>resources/js/Pages/{name}.jsx</code>.</p>
    </main>
  )
}}
''',
    )


def require_name(args: list[str], label: str):
    if not args:
        raise SystemExit(f"Missing {label}.")
    return args[0]


def create_file(path: Path, content: str):
    if path.exists():
        raise SystemExit(f"{path} already exists.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")


def resource_controller_stub(class_name: str):
    return f'''from django.http import JsonResponse


class {class_name}:
    def index(request):
        return JsonResponse({{"action": "index"}})

    def create(request):
        return JsonResponse({{"action": "create"}})

    def store(request):
        return JsonResponse({{"action": "store"}})

    def show(request, id):
        return JsonResponse({{"action": "show", "id": id}})

    def edit(request, id):
        return JsonResponse({{"action": "edit", "id": id}})

    def update(request, id):
        return JsonResponse({{"action": "update", "id": id}})

    def destroy(request, id):
        return JsonResponse({{"action": "destroy", "id": id}})
'''


def new_project(args: list[str]):
    parser = argparse.ArgumentParser(prog="larajango new")
    parser.add_argument("name")
    parsed = parser.parse_args(args)
    destination = Path(parsed.name).resolve()
    if destination.exists():
        raise SystemExit(f"{destination} already exists.")

    source = Path(__file__).resolve().parent.parent
    ignore = shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__", "*.pyc")
    shutil.copytree(source, destination, ignore=ignore)
    artisan = destination / "artisan"
    if artisan.exists():
        artisan.chmod(0o755)
    print(f"Created Larajango project at {destination}")
