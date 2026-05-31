from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse

from larajango.http.request import Request, larajango_request


class FormRequest:
    rules: dict[str, list[str] | str] = {}

    def __init__(self, request):
        self.request = request
        self.larajango = larajango_request(request)
        self.errors: dict[str, list[str]] = {}
        self.cleaned_data: dict[str, str] = {}

    def authorize(self):
        return True

    def prepare_for_validation(self):
        pass

    def passed_validation(self):
        pass

    def validate(self):
        self.prepare_for_validation()
        if not self.authorize():
            self.errors.setdefault("authorization", []).append("This action is unauthorized.")
            return False
        data = self.larajango.input()
        for field, rules in self.rules.items():
            rules = rules if isinstance(rules, list) else rules.split("|")
            value = self.larajango.input(field, "")
            for rule in rules:
                self._check(field, value, rule)
            if field not in self.errors:
                self.cleaned_data[field] = value
        if not self.errors:
            self.passed_validation()
        return not self.errors

    def validated(self):
        return self.cleaned_data

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
            if request.headers.get("Precognition"):
                response = JsonResponse({}, status=204)
                response["Precognition-Success"] = "true"
                return response
            request.validated = form.cleaned_data
            request.form = form
            return action(request, *args, **kwargs)

        return wrapper

    return decorator


__all__ = ["FormRequest", "Request", "larajango_request", "validate"]
