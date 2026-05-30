from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse


class FormRequest:
    rules: dict[str, list[str] | str] = {}

    def __init__(self, request):
        self.request = request
        self.errors: dict[str, list[str]] = {}
        self.cleaned_data: dict[str, str] = {}

    def validate(self):
        data = self.request.POST or self.request.GET
        for field, rules in self.rules.items():
            rules = rules if isinstance(rules, list) else rules.split("|")
            value = data.get(field, "")
            for rule in rules:
                self._check(field, value, rule)
            if field not in self.errors:
                self.cleaned_data[field] = value
        return not self.errors

    def response(self):
        return JsonResponse({"message": "The given data was invalid.", "errors": self.errors}, status=422)

    def _check(self, field: str, value: str, rule: str):
        name, _, arg = rule.partition(":")
        if name == "required" and value in {"", None}:
            self._fail(field, "This field is required.")
        if name == "email" and value:
            try:
                validate_email(value)
            except ValidationError:
                self._fail(field, "Enter a valid email address.")
        if name == "min" and value and len(value) < int(arg):
            self._fail(field, f"Ensure this field has at least {arg} characters.")
        if name == "max" and value and len(value) > int(arg):
            self._fail(field, f"Ensure this field has no more than {arg} characters.")

    def _fail(self, field: str, message: str):
        self.errors.setdefault(field, []).append(message)


def validate(request_class: type[FormRequest]):
    def decorator(action):
        def wrapper(request, *args, **kwargs):
            form = request_class(request)
            if not form.validate():
                return form.response()
            request.validated = form.cleaned_data
            return action(request, *args, **kwargs)

        return wrapper

    return decorator
