from larajango.responses import json, redirect_to, response, view


class ResponseFactory:
    response = staticmethod(response)
    json = staticmethod(json)
    view = staticmethod(view)
    redirect = staticmethod(redirect_to)
