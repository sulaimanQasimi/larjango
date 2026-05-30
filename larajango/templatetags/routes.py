from django import template

from larajango.urls import route

register = template.Library()


@register.simple_tag
def url_for(name, **kwargs):
    return route(name, **kwargs)
