"""Bounded process-local caches for public, file-backed research results."""
from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Callable, Iterable


def _versions(paths: Iterable[Path]) -> tuple:
    versions = []
    for path in paths:
        files = sorted(path.rglob("*.parquet")) if path.is_dir() else [path]
        versions.append(str(path))
        for file in files:
            try:
                stat = file.stat()
                versions.append((str(file), stat.st_mtime_ns, stat.st_size, stat.st_ino))
            except FileNotFoundError:
                versions.append((str(file), None))
    return tuple(versions)


def file_payload_cache(dependencies: Callable[[], Iterable[Path]], *, maxsize: int = 2):
    """Invalidate on source changes; coalesce concurrent reads of the same key.

    Cache small results, not historical panels or authenticated responses.
    Copies isolate callers, and an update during computation is never retained.
    """
    def decorate(function):
        cache: OrderedDict = OrderedDict()
        pending: dict[tuple, Future] = {}
        lock = Lock()

        @wraps(function)
        def wrapped(*args, **kwargs):
            version = _versions(dependencies())
            key = (args, tuple(sorted(kwargs.items())), version)
            with lock:
                if key in cache:
                    cache.move_to_end(key)
                    return deepcopy(cache[key])
                owner = key not in pending
                future = pending.setdefault(key, Future())
            if not owner:
                return deepcopy(future.result())
            try:
                result = function(*args, **kwargs)
                unchanged = version == _versions(dependencies())
                with lock:
                    if unchanged:
                        cache[key] = result
                        while len(cache) > maxsize:
                            cache.popitem(last=False)
                future.set_result(result)
                return deepcopy(result)
            except BaseException as error:
                future.set_exception(error)
                raise
            finally:
                with lock:
                    pending.pop(key, None)

        return wrapped

    return decorate
