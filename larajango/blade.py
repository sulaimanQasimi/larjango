from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.template import TemplateDoesNotExist, engines
from django.utils.html import escape
from django.utils.safestring import mark_safe


class BladeFactory:
    def __init__(self):
        self.custom_directives: dict[str, callable] = {}
        self.custom_conditions: dict[str, callable] = {}
        self.echo_handlers: dict[type, callable] = {}
        self.double_encoding = True

    def render(self, template: str, context: dict | None = None, request=None):
        source = blade_path(template).read_text(encoding="utf-8")
        return self.render_string(source, context, request, origin=template)

    def render_string(self, source: str, context: dict | None = None, request=None, origin: str | None = None):
        compiled = compile_blade(source)
        data = dict(context or {})
        data["__blade"] = self
        data["__blade_origin"] = origin
        data["settings"] = settings
        return engines["django"].from_string(compiled).render(data, request=request)

    def directive(self, name: str, handler):
        self.custom_directives[name] = handler
        return self

    def if_(self, name: str, handler):
        self.custom_conditions[name] = handler
        return self

    def stringable(self, value_type: type, handler):
        self.echo_handlers[value_type] = handler
        return self

    def without_double_encoding(self):
        self.double_encoding = False
        return self

    def echo(self, value):
        for value_type, handler in self.echo_handlers.items():
            if isinstance(value, value_type):
                value = handler(value)
                break
        if self.double_encoding:
            return escape(value)
        return mark_safe(escape(value))

    def raw(self, value):
        return mark_safe(value)


Blade = BladeFactory()


def compile_blade(source: str):
    source, verbatim = _extract_verbatim(source)
    source = _compile_comments(source)
    source = _compile_escaped_at(source)
    source = _compile_custom_directives(source)
    source = _compile_vite(source)
    source = _compile_layouts(source)
    source = _compile_includes(source)
    source = _compile_forms(source)
    source = _compile_stacks(source)
    source = _compile_conditionals(source)
    source = _compile_loops(source)
    source = _compile_echos(source)
    return _restore_verbatim(source, verbatim)


def render_inline(source: str, context: dict | None = None, request=None):
    return Blade.render_string(source, context, request)


def exists(name: str):
    try:
        blade_path(name)
        return True
    except TemplateDoesNotExist:
        return False


def blade_path(name: str):
    name = name.strip("/")
    candidates = [name] if name.endswith(".blade.php") else [f"{name.replace('.', '/')}.blade.php"]
    for candidate in candidates:
        path = Path(settings.BASE_DIR) / "resources" / "views" / candidate
        if path.exists():
            return path
    raise TemplateDoesNotExist(name)


def blade_template_name(name: str):
    return blade_path(name).relative_to(Path(settings.BASE_DIR) / "resources" / "views").as_posix()


def _compile_comments(source: str):
    return re.sub(r"\{\{--.*?--\}\}", "", source, flags=re.S)


def _compile_escaped_at(source: str):
    source = source.replace("@{{", "__BLADE_LITERAL_ECHO__")
    source = source.replace("@@", "__BLADE_LITERAL_AT__")
    return source


def _compile_custom_directives(source: str):
    def replace(match):
        name = match.group("name")
        expression = (match.group("expression") or "").strip()
        if name not in Blade.custom_directives:
            return match.group(0)
        return str(Blade.custom_directives[name](expression))

    return re.sub(r"@(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\((?P<expression>.*?)\))?", replace, source)


def _compile_vite(source: str):
    source = re.sub(r"@viteReactRefresh\b", "{% load vite %}{% vite_react_preamble %}", source)
    source = re.sub(r"@vite\s*\((.*?)\)", lambda m: "{% load vite %}{% vite " + _vite_entries(m.group(1)) + " %}", source)
    return source


def _compile_layouts(source: str):
    source = re.sub(r"@extends\((.*?)\)", lambda m: '{% extends "' + _view_name(_argument(m.group(1))) + '" %}', source)
    source = re.sub(r"@section\((.*?)\)", lambda m: "{% block " + _block_name(_argument(m.group(1))) + " %}", source)
    source = re.sub(r"@(endsection|show|stop)\b", "{% endblock %}", source)
    source = re.sub(
        r"@yield\((.*?)(?:,\s*(.*?))?\)",
        lambda m: "{% block " + _block_name(_argument(m.group(1))) + " %}"
        + (_literal(m.group(2)) if m.group(2) else "")
        + "{% endblock %}",
        source,
    )
    source = re.sub(r"@parent\b", "{{ block.super }}", source)
    return source


def _compile_includes(source: str):
    source = re.sub(r"@include\((.*?)\)", lambda m: '{% include "' + _view_name(_argument(m.group(1))) + '" %}', source)
    source = re.sub(r"@includeIf\((.*?)\)", lambda m: '{% include "' + _view_name(_argument(m.group(1))) + '" ignore missing %}', source)
    return source


def _compile_forms(source: str):
    source = source.replace("@csrf", "{% load forms %}{% csrf %}")
    source = re.sub(r"@method\((.*?)\)", lambda m: '{% load forms %}{% method "' + _argument(m.group(1)).upper() + '" %}', source)
    return source


def _compile_stacks(source: str):
    source = re.sub(
        r"@push\((.*?)\)",
        lambda m: "{% block stack_" + _block_name(_argument(m.group(1))) + " %}{{ block.super }}",
        source,
    )
    source = re.sub(r"@endpush\b", "{% endblock %}", source)
    source = re.sub(
        r"@prepend\((.*?)\)",
        lambda m: "{% block stack_" + _block_name(_argument(m.group(1))) + " %}",
        source,
    )
    source = re.sub(r"@endprepend\b", "{{ block.super }}{% endblock %}", source)
    source = re.sub(
        r"@stack\((.*?)\)",
        lambda m: "{% block stack_" + _block_name(_argument(m.group(1))) + " %}{% endblock %}",
        source,
    )
    source = re.sub(r"@once\b", "", source)
    source = re.sub(r"@endonce\b", "", source)
    return source


def _compile_conditionals(source: str):
    replacements = [
        (r"@if\s*\((.*?)\)", lambda m: "{% if " + _expr(m.group(1)) + " %}"),
        (r"@elseif\s*\((.*?)\)", lambda m: "{% elif " + _expr(m.group(1)) + " %}"),
        (r"@else\b", "{% else %}"),
        (r"@endif\b", "{% endif %}"),
        (r"@unless\s*\((.*?)\)", lambda m: "{% if not " + _expr(m.group(1)) + " %}"),
        (r"@endunless\b", "{% endif %}"),
        (r"@isset\s*\((.*?)\)", lambda m: "{% if " + _expr(m.group(1)) + " is not None %}"),
        (r"@endisset\b", "{% endif %}"),
        (r"@empty\s*\((.*?)\)", lambda m: "{% if not " + _expr(m.group(1)) + " %}"),
        (r"@endempty\b", "{% endif %}"),
        (r"@auth\b(?:\(.*?\))?", "{% if user.is_authenticated %}"),
        (r"@endauth\b", "{% endif %}"),
        (r"@guest\b(?:\(.*?\))?", "{% if not user.is_authenticated %}"),
        (r"@endguest\b", "{% endif %}"),
        (r"@production\b", '{% if settings.APP_ENV == "production" %}'),
        (r"@endproduction\b", "{% endif %}"),
    ]
    for pattern, replacement in replacements:
        source = re.sub(pattern, replacement, source)
    return source


def _compile_loops(source: str):
    source = re.sub(
        r"@foreach\s*\((.*?)\s+as\s+(.*?)\)",
        lambda m: "{% for " + _expr(m.group(2)) + " in " + _expr(m.group(1)) + " %}",
        source,
    )
    source = re.sub(
        r"@forelse\s*\((.*?)\s+as\s+(.*?)\)",
        lambda m: "{% for " + _expr(m.group(2)) + " in " + _expr(m.group(1)) + " %}",
        source,
    )
    source = re.sub(r"@empty\b", "{% empty %}", source)
    source = re.sub(r"@(endforeach|endforelse)\b", "{% endfor %}", source)
    source = re.sub(r"@continue\b(?:\(.*?\))?", "", source)
    source = re.sub(r"@break\b(?:\(.*?\))?", "", source)
    return source


def _compile_echos(source: str):
    source = re.sub(r"\{!!\s*(.*?)\s*!!\}", lambda m: "{{ " + _expr(m.group(1)) + "|safe }}", source, flags=re.S)
    source = re.sub(r"\{\{\s*(.*?)\s*\}\}", lambda m: "{{ " + _expr(m.group(1)) + " }}", source, flags=re.S)
    source = source.replace("__BLADE_LITERAL_ECHO__", "{{")
    source = source.replace("__BLADE_LITERAL_AT__", "@")
    return source


def _extract_verbatim(source: str):
    blocks = []

    def replace(match):
        blocks.append(match.group(1))
        return f"__BLADE_VERBATIM_{len(blocks) - 1}__"

    return re.sub(r"@verbatim(.*?)@endverbatim", replace, source, flags=re.S), blocks


def _restore_verbatim(source: str, blocks: list[str]):
    for index, block in enumerate(blocks):
        source = source.replace(f"__BLADE_VERBATIM_{index}__", block)
    return source


def _argument(value: str):
    return _literal(value.split(",", 1)[0])


def _vite_entries(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        items = re.findall(r"['\"]([^'\"]+)['\"]", value)
        return " ".join(f'"{item}"' for item in items)
    return f'"{_argument(value)}"'


def _literal(value: str | None):
    if not value:
        return ""
    return value.strip().strip("\"'")


def _view_name(value: str):
    if value.endswith(".blade.php") or value.endswith(".html"):
        return value
    try:
        return blade_template_name(value)
    except TemplateDoesNotExist:
        return f"{value.replace('.', '/')}.html"


def _block_name(value: str):
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def _expr(value: str):
    value = value.strip()
    value = re.sub(r"\$(\w+)", r"\1", value)
    value = value.replace("->", ".")
    value = value.replace("===", "==").replace("!==", "!=")
    value = re.sub(r"\btrue\b", "True", value, flags=re.I)
    value = re.sub(r"\bfalse\b", "False", value, flags=re.I)
    value = re.sub(r"\bnull\b", "None", value, flags=re.I)
    value = re.sub(r"count\((.*?)\)", lambda m: _expr(m.group(1)) + "|length", value)
    if value.startswith("!"):
        value = "not " + value[1:].strip()
    return value
