from __future__ import annotations


def dispatch(job):
    if hasattr(job, "handle"):
        return job.handle()
    if callable(job):
        return job()
    raise TypeError("Dispatched jobs must be callable or define handle().")
