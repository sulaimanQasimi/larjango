from importlib import import_module
from pkgutil import iter_modules

from app import Models

for module in iter_modules(Models.__path__):
    if not module.ispkg:
        import_module(f"app.Models.{module.name}")
