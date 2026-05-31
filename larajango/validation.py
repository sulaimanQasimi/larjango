from __future__ import annotations

import enum
import ipaddress
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.http import JsonResponse


MISSING = object()


class ValidationException(Exception):
    def __init__(self, validator, bag: str = "default"):
        super().__init__("The given data was invalid.")
        self.validator = validator
        self.errors = validator.errors()
        self.bag = bag

    def response(self, request=None):
        return JsonResponse({"message": str(self), "errors": self.errors.to_dict()}, status=422)


class MessageBag:
    def __init__(self, messages: dict[str, list[str]] | None = None):
        self.messages = {key: list(value) for key, value in (messages or {}).items()}

    def add(self, key: str, message: str):
        self.messages.setdefault(key, []).append(message)
        return self

    def get(self, key: str):
        return self.messages.get(key, [])

    def first(self, key: str | None = None, default: str = ""):
        if key is not None:
            return next(iter(self.messages.get(key, [])), default)
        return next(iter(self.all()), default)

    def all(self):
        return [message for messages in self.messages.values() for message in messages]

    def any(self):
        return bool(self.messages)

    def has(self, key: str):
        return key in self.messages

    def is_empty(self):
        return not self.any()

    def isEmpty(self):
        return self.is_empty()

    def to_dict(self):
        return dict(self.messages)

    def __bool__(self):
        return self.any()

    def __iter__(self):
        return iter(self.all())


class ValidatedInput(dict):
    def safe(self, keys=None):
        if keys is None:
            return self
        keys = (keys,) if isinstance(keys, str) else tuple(keys)
        return ValidatedInput({key: self[key] for key in keys if key in self})

    def only(self, keys):
        return self.safe(keys)

    def except_(self, keys):
        keys = {keys} if isinstance(keys, str) else set(keys)
        return ValidatedInput({key: value for key, value in self.items() if key not in keys})

    def collect(self):
        return list(self.values())


class Validator:
    def __init__(self, data: dict, rules: dict, messages: dict | None = None, attributes: dict | None = None, extensions: dict | None = None):
        self.data = data or {}
        self.rules = rules or {}
        self.custom_messages = messages or {}
        self.attributes = attributes or {}
        self._errors = MessageBag()
        self._validated = ValidatedInput()
        self._after = []
        self._sometimes = []
        self._stop_on_first_failure = False
        self._ran = False
        self.extensions = extensions or {}

    def passes(self):
        self._run()
        return not self._errors.any()

    def fails(self):
        return not self.passes()

    def validate(self):
        if self.fails():
            raise ValidationException(self)
        return self.validated()

    def validate_with_bag(self, bag: str):
        try:
            return self.validate()
        except ValidationException as exc:
            exc.bag = bag
            raise

    def validateWithBag(self, bag: str):
        return self.validate_with_bag(bag)

    def errors(self):
        self._run()
        return self._errors

    def messages_bag(self):
        return self.errors()

    def messages(self):
        return self.errors()

    def validated(self):
        self._run()
        return ValidatedInput(self._validated)

    def safe(self, keys=None):
        return self.validated().safe(keys)

    def after(self, callback):
        self._after.append(callback)
        return self

    def sometimes(self, attribute, rules, condition):
        self._sometimes.append((attribute, rules, condition))
        return self

    def stop_on_first_failure(self):
        self._stop_on_first_failure = True
        return self

    def stopOnFirstFailure(self):
        return self.stop_on_first_failure()

    def _run(self):
        if self._ran:
            return
        self._ran = True
        rules = dict(self.rules)
        for attribute, conditional_rules, condition in self._sometimes:
            if condition(self.data):
                rules.setdefault(attribute, [])
                rules[attribute] = [*_parse_rules(rules[attribute]), *_parse_rules(conditional_rules)]

        for attribute, attribute_rules in rules.items():
            expanded = _expand_attribute(attribute, self.data)
            for concrete in expanded:
                if not self._validate_attribute(concrete, attribute_rules):
                    if self._stop_on_first_failure:
                        break
            if self._stop_on_first_failure and self._errors.any():
                break

        for callback in self._after:
            callback(self)

    def _validate_attribute(self, attribute: str, attribute_rules):
        rules = _parse_rules(attribute_rules)
        value = _get_dot(self.data, attribute, MISSING)
        present = value is not MISSING
        bail = any(_rule_name(rule) == "bail" for rule in rules)
        nullable = any(_rule_name(rule) == "nullable" for rule in rules)
        sometimes = any(_rule_name(rule) == "sometimes" for rule in rules)
        excluded = any(self._excluded(attribute, value, rule) for rule in rules)
        if excluded:
            return True
        if sometimes and not present:
            return True
        if nullable and value is None:
            if present:
                self._validated[attribute] = value
            return True

        failed = False
        for rule in rules:
            name, params = _parse_rule(rule)
            if name in {"bail", "nullable", "sometimes"} or name.startswith("exclude_"):
                continue
            if not present and not _implicit_rule(name):
                continue
            if self._passes(attribute, value if present else None, name, params):
                continue
            failed = True
            self._fail(attribute, name, params)
            if bail or self._stop_on_first_failure:
                break
        if not failed and present:
            self._validated[attribute] = value
        return not failed

    def _passes(self, attribute, value, name, params):
        other = lambda key, default=MISSING: _get_dot(self.data, key, default)
        empty = _empty(value)
        if callable(name):
            errors = []
            name(attribute, value, lambda message: errors.append(message))
            for message in errors:
                self._errors.add(attribute, message)
            return not errors
        if name in self.extensions:
            return bool(self.extensions[name](attribute, value, params, self))
        if hasattr(name, "validate"):
            errors = []
            name.validate(attribute, value, lambda message: errors.append(message))
            for message in errors:
                self._errors.add(attribute, message)
            return not errors
        if name == "required":
            return not empty
        if name == "required_if":
            return not empty if str(other(params[0], "")) in params[1:] else True
        if name == "required_unless":
            return not empty if str(other(params[0], "")) not in params[1:] else True
        if name == "required_with":
            return not empty if any(not _empty(other(key)) for key in params) else True
        if name == "required_without":
            return not empty if any(_empty(other(key)) for key in params) else True
        if name == "filled":
            return not empty
        if name == "present":
            return value is not MISSING
        if empty:
            return True
        if name in {"accepted", "accepted_if"}:
            if name == "accepted_if" and str(other(params[0], "")) not in params[1:]:
                return True
            return str(value).lower() in {"yes", "on", "1", "true", "accepted"}
        if name in {"declined", "declined_if"}:
            if name == "declined_if" and str(other(params[0], "")) not in params[1:]:
                return True
            return str(value).lower() in {"no", "off", "0", "false", "declined"}
        if name == "boolean":
            return value in {True, False, 0, 1, "0", "1", "true", "false", "True", "False"}
        if name == "string":
            return isinstance(value, str)
        if name == "integer":
            return _integer(value)
        if name == "numeric":
            return _decimal(value) is not None
        if name == "decimal":
            dec = _decimal(value)
            return dec is not None and (not params or len(str(dec).split(".")[-1]) in _decimal_range(params))
        if name == "array":
            return isinstance(value, (dict, list, tuple))
        if name == "list":
            return isinstance(value, list)
        if name == "dict":
            return isinstance(value, dict)
        if name == "email":
            try:
                validate_email(str(value))
                return True
            except DjangoValidationError:
                return False
        if name == "url":
            parsed = urlparse(str(value))
            schemes = set(params or ["http", "https"])
            return bool(parsed.scheme in schemes and parsed.netloc)
        if name == "active_url":
            return self._passes(attribute, value, "url", params)
        if name == "ip":
            return _ip(value) is not None
        if name == "ipv4":
            return isinstance(_ip(value), ipaddress.IPv4Address)
        if name == "ipv6":
            return isinstance(_ip(value), ipaddress.IPv6Address)
        if name == "uuid":
            try:
                uuid.UUID(str(value))
                return True
            except ValueError:
                return False
        if name == "ulid":
            return bool(re.fullmatch(r"[0-7][0-9A-HJKMNP-TV-Z]{25}", str(value)))
        if name == "json":
            try:
                json.loads(value if isinstance(value, str) else json.dumps(value))
                return True
            except (TypeError, ValueError):
                return False
        if name == "date":
            return _date(value) is not None
        if name in {"before", "before_or_equal", "after", "after_or_equal"}:
            left = _date(value)
            right = _date(other(params[0], params[0]))
            if not left or not right:
                return False
            if name == "before":
                return left < right
            if name == "before_or_equal":
                return left <= right
            if name == "after":
                return left > right
            return left >= right
        if name == "same":
            return value == other(params[0])
        if name == "different":
            return value != other(params[0])
        if name == "confirmed":
            return value == other(f"{attribute}_confirmation")
        if name == "in":
            return str(value) in params
        if name == "not_in":
            return str(value) not in params
        if name == "regex":
            return re.search(params[0], str(value)) is not None
        if name == "not_regex":
            return re.search(params[0], str(value)) is None
        if name == "alpha":
            return bool(re.fullmatch(r"[A-Za-z]+", str(value)))
        if name == "alpha_num":
            return bool(re.fullmatch(r"[A-Za-z0-9]+", str(value)))
        if name == "alpha_dash":
            return bool(re.fullmatch(r"[A-Za-z0-9_-]+", str(value)))
        if name == "ascii":
            return all(ord(ch) < 128 for ch in str(value))
        if name == "lowercase":
            return str(value).lower() == str(value)
        if name == "uppercase":
            return str(value).upper() == str(value)
        if name == "starts_with":
            return str(value).startswith(tuple(params))
        if name == "ends_with":
            return str(value).endswith(tuple(params))
        if name == "doesnt_start_with":
            return not str(value).startswith(tuple(params))
        if name == "doesnt_end_with":
            return not str(value).endswith(tuple(params))
        if name == "hex_color":
            return bool(re.fullmatch(r"#(?:[0-9a-fA-F]{3}){1,2}", str(value)))
        if name == "mac_address":
            return bool(re.fullmatch(r"[0-9a-fA-F]{2}([-:])[0-9a-fA-F]{2}(?:\1[0-9a-fA-F]{2}){4}", str(value)))
        if name in {"min", "max", "size"}:
            size = _size(value)
            target = Decimal(params[0])
            return {"min": size >= target, "max": size <= target, "size": size == target}[name]
        if name == "between":
            size = _size(value)
            return Decimal(params[0]) <= size <= Decimal(params[1])
        if name == "digits":
            return str(value).isdigit() and len(str(value)) == int(params[0])
        if name == "digits_between":
            return str(value).isdigit() and int(params[0]) <= len(str(value)) <= int(params[1])
        if name == "multiple_of":
            dec = _decimal(value)
            return dec is not None and dec % Decimal(params[0]) == 0
        if name == "timezone":
            try:
                from zoneinfo import ZoneInfo

                ZoneInfo(str(value))
                return True
            except Exception:
                return False
        if name == "enum" and params:
            enum_class = params[0]
            if isinstance(enum_class, type) and issubclass(enum_class, enum.Enum):
                try:
                    enum_class(value)
                    return True
                except ValueError:
                    return False
        if name == "file":
            return hasattr(value, "size") and hasattr(value, "name")
        if name == "image":
            return hasattr(value, "content_type") and str(value.content_type).startswith("image/")
        if name == "mimes":
            extension = str(getattr(value, "name", "")).rsplit(".", 1)[-1].lower()
            return extension in {item.lower() for item in params}
        if name == "mimetypes":
            return getattr(value, "content_type", None) in params
        if name == "unique":
            return _database_unique(value, attribute, params)
        if name == "exists":
            return _database_exists(value, attribute, params)
        return True

    def _excluded(self, attribute, value, rule):
        name, params = _parse_rule(rule)
        other = lambda key, default=MISSING: _get_dot(self.data, key, default)
        if name == "exclude":
            return True
        if name == "exclude_if":
            return str(other(params[0], "")) in params[1:]
        if name == "exclude_unless":
            return str(other(params[0], "")) not in params[1:]
        if name == "exclude_without":
            return _empty(other(params[0]))
        return False

    def _fail(self, attribute, rule, params):
        key = f"{attribute}.{rule}"
        message = self.custom_messages.get(key) or self.custom_messages.get(rule) or DEFAULT_MESSAGES.get(rule) or DEFAULT_MESSAGES["default"]
        message = message.replace(":attribute", self.attributes.get(attribute, attribute.replace("_", " ")))
        if params:
            message = message.replace(":value", str(params[0])).replace(":min", str(params[0])).replace(":max", str(params[-1]))
            message = message.replace(":other", str(params[0])).replace(":size", str(params[0]))
        self._errors.add(attribute, message)


class ValidatorFactory:
    def __init__(self):
        self.extensions: dict[str, callable] = {}
        self.replacers: dict[str, callable] = {}

    def make(self, data: dict, rules: dict, messages: dict | None = None, attributes: dict | None = None):
        validator = Validator(data, rules, messages, attributes, self.extensions)
        return validator

    def validate(self, data: dict, rules: dict, messages: dict | None = None, attributes: dict | None = None):
        return self.make(data, rules, messages, attributes).validate()

    def extend(self, rule: str, callback):
        self.extensions[rule] = callback
        return self


ValidatorFacade = ValidatorFactory()


class Rule:
    @staticmethod
    def in_(values):
        return "in:" + ",".join(str(value) for value in values)

    @staticmethod
    def not_in(values):
        return "not_in:" + ",".join(str(value) for value in values)

    @staticmethod
    def unique(table, column=None):
        return DatabaseRule("unique", table, column)

    @staticmethod
    def exists(table, column=None):
        return DatabaseRule("exists", table, column)

    @staticmethod
    def when(condition, rules, default=()):
        return rules if condition else default

    @staticmethod
    def required_if(condition):
        return RequiredIf(condition)


@dataclass
class DatabaseRule:
    name: str
    table: str | type
    column: str | None = None
    ignore_value: object = None
    ignore_column: str = "pk"

    def ignore(self, value, column: str = "pk"):
        self.ignore_value = getattr(value, "pk", value)
        self.ignore_column = column
        return self

    def __str__(self):
        pieces = [self.name, str(self.table)]
        if self.column:
            pieces.append(self.column)
        if self.ignore_value is not None:
            pieces.extend([str(self.ignore_value), self.ignore_column])
        return ":".join([pieces[0], ",".join(pieces[1:])])


class RequiredIf:
    def __init__(self, condition):
        self.condition = condition


DEFAULT_MESSAGES = {
    "default": "The :attribute is invalid.",
    "required": "The :attribute field is required.",
    "required_if": "The :attribute field is required.",
    "required_unless": "The :attribute field is required.",
    "required_with": "The :attribute field is required.",
    "required_without": "The :attribute field is required.",
    "filled": "The :attribute field must have a value.",
    "present": "The :attribute field must be present.",
    "accepted": "The :attribute field must be accepted.",
    "declined": "The :attribute field must be declined.",
    "boolean": "The :attribute field must be true or false.",
    "email": "The :attribute must be a valid email address.",
    "min": "The :attribute must be at least :min.",
    "max": "The :attribute must not be greater than :max.",
    "size": "The :attribute must be :size.",
    "between": "The :attribute must be between :min and :max.",
    "same": "The :attribute and :other must match.",
    "different": "The :attribute and :other must be different.",
    "confirmed": "The :attribute confirmation does not match.",
    "unique": "The :attribute has already been taken.",
    "exists": "The selected :attribute is invalid.",
}


def _parse_rules(rules):
    if rules is None:
        return []
    if isinstance(rules, str):
        return [rule for rule in rules.split("|") if rule]
    if isinstance(rules, (list, tuple)):
        expanded = []
        for rule in rules:
            if isinstance(rule, RequiredIf):
                if rule.condition:
                    expanded.append("required")
            elif isinstance(rule, DatabaseRule):
                expanded.append(str(rule))
            elif isinstance(rule, str) and "|" in rule:
                expanded.extend(_parse_rules(rule))
            elif rule:
                expanded.append(rule)
        return expanded
    return [rules]


def _parse_rule(rule):
    if not isinstance(rule, str):
        return rule, []
    name, _, raw = rule.partition(":")
    return name, _split_params(raw)


def _rule_name(rule):
    return _parse_rule(rule)[0]


def _split_params(raw):
    return [] if raw == "" else [part.strip() for part in raw.split(",")]


def _implicit_rule(name):
    return name in {"required", "required_if", "required_unless", "required_with", "required_without", "accepted", "declined", "present"}


def _empty(value):
    return value is MISSING or value is None or value == "" or value == [] or value == {}


def _get_dot(data, key, default=None):
    key = str(key).replace("\\.", "__DOT__")
    current = data
    for part in key.split("."):
        part = part.replace("__DOT__", ".")
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        elif isinstance(current, (list, tuple)) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return default
            current = current[index]
        else:
            return getattr(current, part, default)
    return current


def _expand_attribute(attribute, data):
    if "*" not in attribute:
        return [attribute]
    prefix, _, suffix = attribute.partition(".*.")
    items = _get_dot(data, prefix, [])
    if isinstance(items, dict):
        return [f"{prefix}.{key}.{suffix}" for key in items]
    return [f"{prefix}.{index}.{suffix}" for index, _ in enumerate(items)]


def _integer(value):
    try:
        return str(int(value)) == str(value) or isinstance(value, int)
    except (TypeError, ValueError):
        return False


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _decimal_range(params):
    if len(params) == 1:
        return {int(params[0])}
    return set(range(int(params[0]), int(params[1]) + 1))


def _date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if value == "today":
        return datetime.combine(date.today(), datetime.min.time())
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _ip(value):
    try:
        return ipaddress.ip_address(str(value))
    except ValueError:
        return None


def _size(value):
    dec = _decimal(value)
    if dec is not None:
        return dec
    if hasattr(value, "size"):
        return Decimal(value.size)
    return Decimal(len(value))


def _database_model(table):
    if isinstance(table, type) and hasattr(table, "objects"):
        return table
    if isinstance(table, str):
        try:
            from django.apps import apps

            return apps.get_model("app", table[:1].upper() + table[1:].rstrip("s"))
        except Exception:
            return None
    return None


def _database_unique(value, attribute, params):
    model = _database_model(params[0]) if params else None
    if model is None:
        return True
    column = params[1] if len(params) > 1 else attribute
    qs = model.objects.filter(**{column: value})
    if len(params) > 2:
        ignore = params[2]
        ignore_column = params[3] if len(params) > 3 else "pk"
        qs = qs.exclude(**{ignore_column: ignore})
    return not qs.exists()


def _database_exists(value, attribute, params):
    model = _database_model(params[0]) if params else None
    if model is None:
        return True
    column = params[1] if len(params) > 1 else attribute
    return model.objects.filter(**{column: value}).exists()
