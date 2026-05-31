from __future__ import annotations


class Middleware:
    def __init__(self, router):
        self.router = router

    def alias(self, aliases: dict[str, str | callable]):
        for name, middleware in aliases.items():
            self.router.alias_middleware(name, middleware)
        return self

    def group(self, name: str, middleware):
        self.router.middleware_group(name, middleware)
        return self

    def append_to_group(self, name: str, middleware):
        self.router.append_to_group(name, middleware)
        return self

    def prepend_to_group(self, name: str, middleware):
        self.router.prepend_to_group(name, middleware)
        return self

    def web(self, append=(), prepend=(), replace=None, remove=()):
        return self._patch_group("web", append, prepend, replace or {}, remove)

    def api(self, append=(), prepend=(), replace=None, remove=()):
        return self._patch_group("api", append, prepend, replace or {}, remove)

    def priority(self, middleware):
        self.router.middleware_priority = tuple(middleware)
        return self

    def prevent_request_forgery(
        self,
        except_paths=(),
        origin_only: bool = False,
        allow_same_site: bool = False,
        xsrf_cookie: bool = True,
    ):
        from larajango.csrf import configure_csrf

        configure_csrf(
            except_paths=except_paths,
            origin_only=origin_only,
            allow_same_site=allow_same_site,
            xsrf_cookie=xsrf_cookie,
        )
        return self

    def preventRequestForgery(
        self,
        except_paths=(),
        origin_only: bool = False,
        allow_same_site: bool = False,
        xsrf_cookie: bool = True,
    ):
        return self.prevent_request_forgery(
            except_paths=except_paths,
            origin_only=origin_only,
            allow_same_site=allow_same_site,
            xsrf_cookie=xsrf_cookie,
        )

    def trim_strings(self, except_=()):
        from larajango.middleware import configure_trim_strings

        configure_trim_strings(except_=except_)
        return self

    def trimStrings(self, except_=()):
        return self.trim_strings(except_=except_)

    def convert_empty_strings_to_null(self, except_=()):
        from larajango.middleware import configure_empty_strings

        configure_empty_strings(except_=except_)
        return self

    def convertEmptyStringsToNull(self, except_=()):
        return self.convert_empty_strings_to_null(except_=except_)

    def trust_proxies(self, at=(), headers=()):
        from larajango.middleware import configure_trusted_proxies

        configure_trusted_proxies(at=at, headers=headers)
        return self

    def trustProxies(self, at=(), headers=()):
        return self.trust_proxies(at=at, headers=headers)

    def trust_hosts(self, at=(), subdomains: bool = True):
        from larajango.middleware import configure_trusted_hosts

        configure_trusted_hosts(at=at, subdomains=subdomains)
        return self

    def trustHosts(self, at=(), subdomains: bool = True):
        return self.trust_hosts(at=at, subdomains=subdomains)

    def _patch_group(self, name, append, prepend, replace, remove):
        group = list(self.router.middleware_groups.get(name, ()))
        for old, new in replace.items():
            group = [new if item == old else item for item in group]
        group = [item for item in group if item not in remove]
        group = [*_as_tuple(prepend), *group, *_as_tuple(append)]
        self.router.middleware_group(name, group)
        return self


def _as_tuple(value):
    if value is None:
        return ()
    if isinstance(value, str) or callable(value):
        return (value,)
    return tuple(value)
