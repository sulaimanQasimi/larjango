from django import template
from django.middleware.csrf import get_token
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def method(verb):
    return format_html('<input type="hidden" name="_method" value="{}">', str(verb).upper())


@register.simple_tag(takes_context=True)
def csrf(context):
    request = context["request"]
    return format_html('<input type="hidden" name="csrfmiddlewaretoken" value="{}">', get_token(request))


@register.simple_tag(takes_context=True)
def csrf_meta(context):
    request = context["request"]
    return format_html('<meta name="csrf-token" content="{}">', get_token(request))
