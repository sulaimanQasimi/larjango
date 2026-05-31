from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

from django.core.cache import cache
from django.http import HttpResponse


MISSING = object()
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class SessionStore:
    def __init__(self, request):
        self.request = request
        self.backend = request.session

    def get(self, key: str, default=None):
        value = _get_dot(self.backend, key, MISSING)
        if value is MISSING:
            return default() if callable(default) else default
        return value

    def all(self):
        return dict(self.backend.items())

    def only(self, keys):
        return {key: self.get(key) for key in _keys(keys) if self.exists(key)}

    def except_(self, keys):
        blocked = set(_keys(keys))
        return {key: value for key, value in self.backend.items() if key not in blocked}

    def put(self, key: str | dict, value=MISSING):
        if isinstance(key, dict):
            for item_key, item_value in key.items():
                _set_dot(self.backend, item_key, item_value)
        else:
            _set_dot(self.backend, key, value)
        self.backend.modified = True
        return self

    def push(self, key: str, value):
        items = self.get(key, [])
        if not isinstance(items, list):
            items = [items]
        items.append(value)
        return self.put(key, items)

    def pull(self, key: str, default=None):
        value = self.get(key, default)
        self.forget(key)
        return value

    def increment(self, key: str, amount: int = 1):
        value = int(self.get(key, 0)) + amount
        self.put(key, value)
        return value

    def decrement(self, key: str, amount: int = 1):
        return self.increment(key, -amount)

    def has(self, key):
        return all(self.get(item, MISSING) is not MISSING and self.get(item) is not None for item in _keys(key))

    def exists(self, key):
        return all(self.get(item, MISSING) is not MISSING for item in _keys(key))

    def missing(self, key):
        return not self.exists(key)

    def flash(self, key: str, value):
        self.put(key, value)
        new = set(self.backend.get("_flash_new", []))
        new.add(key)
        self.backend["_flash_new"] = list(new)
        self.backend.modified = True
        return self

    def now(self, key: str, value):
        self.put(key, value)
        old = set(self.backend.get("_flash_old", []))
        old.add(key)
        self.backend["_flash_old"] = list(old)
        self.backend.modified = True
        return self

    def reflash(self):
        old = set(self.backend.get("_flash_old", []))
        new = set(self.backend.get("_flash_new", []))
        self.backend["_flash_new"] = list(new | old)
        self.backend["_flash_old"] = []
        self.backend.modified = True
        return self

    def keep(self, keys):
        keys = set(_keys(keys))
        old = set(self.backend.get("_flash_old", []))
        new = set(self.backend.get("_flash_new", []))
        self.backend["_flash_new"] = list(new | (old & keys))
        self.backend["_flash_old"] = list(old - keys)
        self.backend.modified = True
        return self

    def forget(self, keys):
        for key in _keys(keys):
            _forget_dot(self.backend, key)
        self.backend.modified = True
        return self

    def flush(self):
        self.backend.flush()
        return self

    def regenerate(self, destroy: bool = False):
        self.backend.cycle_key()
        if destroy:
            self.backend.clear()
        return True

    def invalidate(self):
        self.backend.flush()
        return True

    def token(self):
        return self.backend.session_key

    def cache(self):
        return SessionCache(self)

    @classmethod
    def start_request(cls, request):
        session = request.session
        if "_flash_new" in session:
            session["_flash_old"] = session.get("_flash_new", [])
            session["_flash_new"] = []
            session.modified = True

    @classmethod
    def end_request(cls, request):
        session = request.session
        old = list(session.get("_flash_old", []))
        for key in old:
            session.pop(key, None)
        if old:
            session["_flash_old"] = []
            session.modified = True


class SessionCache:
    def __init__(self, session: SessionStore):
        self.session = session

    def key(self, key: str):
        session_key = self.session.backend.session_key or "anonymous"
        return f"session:{session_key}:{key}"

    def get(self, key: str, default=None):
        value = cache.get(self.key(key), MISSING)
        return default if value is MISSING else value

    def put(self, key: str, value, seconds=None):
        cache.set(self.key(key), value, _seconds(seconds))
        return True

    def set(self, key: str, value, seconds=None):
        return self.put(key, value, seconds)

    def remember(self, key: str, seconds, callback):
        value = self.get(key, MISSING)
        if value is not MISSING:
            return value
        value = callback()
        self.put(key, value, seconds)
        return value

    def forget(self, key: str):
        cache.delete(self.key(key))
        return True

    def has(self, key: str):
        return self.get(key, MISSING) is not MISSING


class SessionManager:
    drivers: dict[str, callable] = {}

    def __init__(self):
        self._request = None

    def set_request(self, request):
        self._request = request
        return self

    def from_request(self, request):
        return SessionStore(request)

    def store(self):
        if self._request is None:
            raise RuntimeError("No active request is bound to the session manager.")
        return SessionStore(self._request)

    def extend(self, name: str, resolver):
        self.drivers[name] = resolver
        return self

    def __call__(self, key=None, default=None):
        if key is None:
            return self.store()
        if isinstance(key, dict):
            return self.store().put(key)
        return self.store().get(key, default)

    def __getattr__(self, name):
        return getattr(self.store(), name)


Session = SessionManager()


def session(key=None, default=None):
    return Session(key, default)


def flash(request, key: str, value):
    return SessionStore(request).flash(key, value)


def flashed(request, key: str, default=None):
    return SessionStore(request).pull(key, default)


def old(request, key: str, default=""):
    return request.session.get("_old_input", {}).get(key, default)


def flash_input(request):
    return SessionStore(request).flash("_old_input", dict(request.POST))


@contextmanager
def session_lock(request, lock_seconds: int = 10, wait_seconds: int = 10):
    key = request.session.session_key
    if not key:
        request.session.save()
        key = request.session.session_key
    lock = _lock_for(key)
    acquired = lock.acquire(timeout=wait_seconds)
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        lock.release()


class StartSession:
    def __init__(self, next_handler):
        self.next_handler = next_handler

    def __call__(self, request, *args, **kwargs):
        Session.set_request(request)
        SessionStore.start_request(request)
        response = self.next_handler(request, *args, **kwargs)
        SessionStore.end_request(request)
        return response


class BlockSession:
    def __init__(self, next_handler, lock_seconds: str = "10", wait_seconds: str = "10"):
        self.next_handler = next_handler
        self.lock_seconds = int(lock_seconds)
        self.wait_seconds = int(wait_seconds)

    def __call__(self, request, *args, **kwargs):
        with session_lock(request, self.lock_seconds, self.wait_seconds) as acquired:
            if not acquired:
                return HttpResponse("Session lock timeout.", status=423)
            return self.next_handler(request, *args, **kwargs)


def _keys(keys):
    if isinstance(keys, str):
        return (keys,)
    return tuple(keys)


def _get_dot(data, key, default=None):
    current = data
    for part in str(key).split("."):
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        else:
            try:
                current = current[part]
            except (KeyError, TypeError):
                return default
    return current


def _set_dot(data, key, value):
    parts = str(key).split(".")
    current = data
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _forget_dot(data, key):
    parts = str(key).split(".")
    current = data
    for part in parts[:-1]:
        current = current.get(part)
        if not isinstance(current, dict):
            return
    current.pop(parts[-1], None)


def _seconds(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return max(0, int(value.timestamp() - time.time()))
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return int(value)


def _lock_for(key: str):
    with _locks_guard:
        if key not in _locks:
            _locks[key] = threading.Lock()
        return _locks[key]
