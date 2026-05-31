from django import template

from larajango.validation import MessageBag

register = template.Library()


@register.simple_tag(takes_context=True)
def errors(context, bag="default"):
    request = context.get("request")
    if request is None:
        return MessageBag()
    return MessageBag(request.session.get("_errors", {}).get(bag, {}))


@register.simple_tag(takes_context=True)
def error(context, key, bag="default"):
    return errors(context, bag).first(key)


@register.simple_tag(takes_context=True)
def old(context, key, default=""):
    request = context.get("request")
    if request is None:
        return default
    return request.session.get("_old_input", {}).get(key, default)
