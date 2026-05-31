from django import template

from larajango.assets import Vite, vite_asset, vite_client, vite_react_refresh, vite_tags

register = template.Library()


@register.simple_tag
def vite(*entries):
    return vite_tags(entries or None)


@register.simple_tag
def vite_asset_url(entry):
    return vite_asset(entry)


@register.simple_tag
def vite_hmr_client():
    return vite_client()


@register.simple_tag
def vite_react_preamble():
    return vite_react_refresh()


@register.simple_tag
def vite_prefetch(*entries):
    return "".join(str(tag) for tag in Vite.prefetch_tags(entries or Vite.entrypoints))


@register.simple_tag
def vite_csp_nonce():
    return Vite.csp_nonce() or ""
