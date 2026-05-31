from django import template

from larajango.urls import action, route, signed_route, temporary_signed_route, url

register = template.Library()


@register.simple_tag
def url_for(name, **kwargs):
    return route(name, **kwargs)


@register.simple_tag
def route_url(name, **kwargs):
    return route(name, kwargs)


@register.simple_tag
def signed_url(name, **kwargs):
    return signed_route(name, kwargs)


@register.simple_tag
def temporary_signed_url(name, expiration, **kwargs):
    return temporary_signed_route(name, expiration, kwargs)


@register.simple_tag
def action_url(target, **kwargs):
    return action(target, kwargs)


@register.simple_tag
def url_to(path="/", **kwargs):
    return url(path, kwargs)
