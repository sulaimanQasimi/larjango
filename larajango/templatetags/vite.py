from django import template

from larajango.assets import vite_asset

register = template.Library()


@register.simple_tag
def vite(entry):
    return vite_asset(entry)
