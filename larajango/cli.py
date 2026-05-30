from __future__ import annotations

import argparse
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
    if command == "route:list":
        return route_list()
    if command == "make:controller":
        return make_controller(args)
    if command == "make:model":
        return make_model(args)
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
  ./artisan route:list
  ./artisan make:controller NameController
  ./artisan make:model Name
  ./artisan inertia:page Dashboard/Index
  python -m larajango new project_name
"""
    )


def route_list():
    import routes.web  # noqa: F401
    from larajango.routing import router

    print(f"{'METHOD':<8} {'URI':<28} {'NAME':<24} ACTION")
    print("-" * 88)
    for route in router.routes:
        action = f"{route.action.__module__}.{route.action.__qualname__}"
        print(f"{route.method:<8} {route.uri:<28} {(route.name or ''):<24} {action}")


def make_controller(args: list[str]):
    name = require_name(args, "controller name")
    class_name = name if name.endswith("Controller") else f"{name}Controller"
    path = ROOT / "app" / "Http" / "Controllers" / f"{class_name}.py"
    create_file(
        path,
        f'''from larajango.inertia import inertia


class {class_name}:
    def index(request):
        return inertia(request, "{class_name.removesuffix("Controller")}/Index", {{}})
''',
    )


def make_model(args: list[str]):
    name = require_name(args, "model name")
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
