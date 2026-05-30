from __future__ import annotations

import argparse
from datetime import datetime
from importlib import import_module
import json
import os
import secrets
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
    if command == "route:cache":
        return route_cache()
    if command == "route:clear":
        return route_clear()
    if command == "config:show":
        return config_show(args)
    if command == "config:clear":
        return config_clear()
    if command == "cache:clear":
        return cache_clear()
    if command == "db:seed":
        return db_seed(args)
    if command == "key:generate":
        return key_generate()
    if command == "storage:link":
        return storage_link()
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
    if command == "make:policy":
        return make_policy(args)
    if command == "make:job":
        return make_job(args)
    if command == "make:provider":
        return make_provider(args)
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
  ./artisan route:cache
  ./artisan route:clear
  ./artisan config:show app
  ./artisan config:clear
  ./artisan cache:clear
  ./artisan db:seed
  ./artisan key:generate
  ./artisan storage:link
  ./artisan make:controller NameController
  ./artisan make:model Name
  ./artisan make:middleware EnsureUserIsAdmin
  ./artisan make:request StorePostRequest
  ./artisan make:seeder UserSeeder
  ./artisan make:policy PostPolicy
  ./artisan make:job SendWelcomeEmail
  ./artisan make:provider AppServiceProvider
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
    parser.add_argument("-vv", "--very-verbose", action="store_true")
    parser.add_argument("--except-vendor", action="store_true")
    parser.add_argument("--only-vendor", action="store_true")
    parsed = parser.parse_args(args)

    import routes.web  # noqa: F401
    try:
        import routes.api  # noqa: F401
    except ModuleNotFoundError:
        pass
    from larajango.routing import router

    show_middleware = parsed.verbose or parsed.very_verbose
    middleware_header = " MIDDLEWARE" if show_middleware else ""
    domain_header = " DOMAIN" if parsed.very_verbose else ""
    print(f"{'METHOD':<18} {'URI':<30} {'NAME':<24} ACTION{middleware_header}{domain_header}")
    print("-" * (125 if parsed.very_verbose else 105 if show_middleware else 92))
    for route in router.routes:
        if parsed.path and not route.uri.strip("/").startswith(parsed.path.strip("/")):
            continue
        is_vendor = route.action.__module__.startswith("larajango.") if callable(route.action) else False
        if parsed.except_vendor and is_vendor:
            continue
        if parsed.only_vendor and not is_vendor:
            continue
        action = f"{route.action.__module__}.{route.action.__qualname__}" if callable(route.action) else str(route.action)
        methods = "|".join(route.methods)
        middleware = ", ".join(str(item) for item in route.middleware)
        suffix = f" {middleware}" if show_middleware else ""
        suffix += f" {route.domain or ''}" if parsed.very_verbose else ""
        print(f"{methods:<18} {route.uri:<30} {(route.name or ''):<24} {action}{suffix}")


def route_cache():
    import routes.web  # noqa: F401
    try:
        import routes.api  # noqa: F401
    except ModuleNotFoundError:
        pass
    from larajango.routing import router

    cache_path = ROOT / "bootstrap" / "cache" / "routes.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "methods": route.methods,
            "uri": route.uri,
            "name": route.name,
            "middleware": [str(item) for item in route.middleware],
            "domain": route.domain,
            "constraints": route.constraints,
            "action": f"{route.action.__module__}.{route.action.__qualname__}" if callable(route.action) else str(route.action),
        }
        for route in router.routes
    ]
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Routes cached to {cache_path}.")


def route_clear():
    cache_path = ROOT / "bootstrap" / "cache" / "routes.json"
    if cache_path.exists():
        cache_path.unlink()
    print("Route cache cleared.")


def config_show(args: list[str]):
    namespace = require_name(args, "config namespace")
    module = import_module(f"config.{namespace}")
    for key in sorted(name for name in dir(module) if name.isupper()):
        print(f"{namespace}.{key.lower()}={getattr(module, key)}")


def config_clear():
    from larajango.config import config

    config.cache_clear()
    print("Configuration cache cleared.")


def cache_clear():
    from django.core.cache import cache

    cache.clear()
    print("Application cache cleared.")


def db_seed(args: list[str]):
    class_name = args[0] if args else "DatabaseSeeder"
    module = import_module(f"database.seeders.{class_name}")
    seeder = getattr(module, class_name)()
    seeder.run()
    print(f"Seeded with {class_name}.")


def key_generate():
    key = "base64:" + secrets.token_urlsafe(48)
    env_path = ROOT / ".env"
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        example = ROOT / ".env.example"
        lines = example.read_text(encoding="utf-8").splitlines() if example.exists() else []

    replaced = False
    next_lines = []
    for line in lines:
        if line.startswith("APP_KEY="):
            next_lines.append(f"APP_KEY={key}")
            replaced = True
        else:
            next_lines.append(line)
    if not replaced:
        next_lines.append(f"APP_KEY={key}")

    env_path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    print("Application key set successfully.")


def storage_link():
    public_link = ROOT / "public" / "storage"
    target = ROOT / "storage" / "app" / "public"
    target.mkdir(parents=True, exist_ok=True)
    public_link.parent.mkdir(parents=True, exist_ok=True)
    if public_link.exists():
        print("The public storage link already exists.")
        return
    public_link.symlink_to(target, target_is_directory=True)
    print(f"Linked {public_link} -> {target}")


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


def make_policy(args: list[str]):
    name = require_name(args, "policy name")
    class_name = name if name.endswith("Policy") else f"{name}Policy"
    path = ROOT / "app" / "Policies" / f"{class_name}.py"
    create_file(
        path,
        f'''class {class_name}:
    def view(self, user, model):
        return True

    def create(self, user):
        return user.is_authenticated

    def update(self, user, model):
        return user.is_authenticated

    def delete(self, user, model):
        return user.is_authenticated
''',
    )


def make_job(args: list[str]):
    name = require_name(args, "job name")
    path = ROOT / "app" / "Jobs" / f"{name}.py"
    create_file(
        path,
        f'''class {name}:
    def handle(self):
        pass
''',
    )


def make_provider(args: list[str]):
    name = require_name(args, "provider name")
    class_name = name if name.endswith("Provider") else f"{name}Provider"
    path = ROOT / "app" / "Providers" / f"{class_name}.py"
    create_file(
        path,
        f'''from larajango.foundation import ServiceProvider


class {class_name}(ServiceProvider):
    def register(self):
        pass

    def boot(self):
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
