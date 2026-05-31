from __future__ import annotations

from django.http import JsonResponse

from larajango.http.request import Request, larajango_request
from larajango.responses import back
from larajango.validation import ValidationException, ValidatorFacade


class FormRequest:
    rules: dict[str, list[str] | str] = {}
    messages: dict[str, str] = {}
    attributes: dict[str, str] = {}
    error_bag = "default"
    stop_on_first_failure = False

    def __init__(self, request):
        self.request = request
        self.larajango = larajango_request(request)
        self.errors = {}
        self.cleaned_data = {}
        self.validator = None

    def authorize(self):
        return True

    def prepare_for_validation(self):
        pass

    def passed_validation(self):
        pass

    def validation_rules(self):
        return self.rules() if callable(self.rules) else self.rules

    def validation_messages(self):
        return self.messages() if callable(self.messages) else self.messages

    def validation_attributes(self):
        return self.attributes() if callable(self.attributes) else self.attributes

    def with_validator(self, validator):
        pass

    def after(self):
        return []

    def validate(self):
        self.prepare_for_validation()
        if not self.authorize():
            self.errors = {"authorization": ["This action is unauthorized."]}
            return False
        validator = ValidatorFacade.make(
            self.larajango.input(),
            self.validation_rules(),
            self.validation_messages(),
            self.validation_attributes(),
        )
        if self.stop_on_first_failure:
            validator.stop_on_first_failure()
        self.with_validator(validator)
        for callback in self.after():
            validator.after(callback)
        self.validator = validator
        if validator.fails():
            self.errors = validator.errors().to_dict()
            return False
        self.cleaned_data = validator.validated()
        self.passed_validation()
        return True

    def validated(self, key=None, default=None):
        if key is None:
            return self.cleaned_data
        return self.cleaned_data.get(key, default)

    def safe(self, keys=None):
        return self.validator.safe(keys) if self.validator else self.cleaned_data

    def response(self):
        return validation_failed_response(self.request, self.errors, self.error_bag)


def validation_failed_response(request, errors: dict, bag: str = "default"):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({"message": "The given data was invalid.", "errors": errors}, status=422)
    request.session.setdefault("_errors", {})
    request.session["_errors"][bag] = errors
    if hasattr(request, "larajango"):
        request.larajango.flash()
    return back(request).with_input(request).to_response()


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


def validate_data(data: dict, rules: dict, messages: dict | None = None, attributes: dict | None = None):
    return ValidatorFacade.validate(data, rules, messages, attributes)


__all__ = ["FormRequest", "Request", "ValidationException", "larajango_request", "validate", "validate_data"]
