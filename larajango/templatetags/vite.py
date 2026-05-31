from django import template

from larajango.assets import vite_asset, vite_client, vite_react_refresh

register = template.Library()


@register.simple_tag
def vite(entry):
    return vite_asset(entry)


@register.simple_tag
def vite_hmr_client():
    return vite_client()


@register.simple_tag
def vite_react_preamble():
    return vite_react_refresh()
