from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def method(verb):
    return format_html('<input type="hidden" name="_method" value="{}">', str(verb).upper())
