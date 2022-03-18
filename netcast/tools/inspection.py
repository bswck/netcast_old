from __future__ import annotations  # Python 3.8

import functools
import inspect
import re
from types import MethodType
from typing import Any, Callable

from netcast.constants import MISSING


def is_classmethod(cls: type, method: MethodType) -> bool:
    return getattr(method, "__self__", None) is cls


def match_params(func: Callable, kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    def foo(baz, /, bar, biz):
        pass

    def bar(foo, **baz):
        pass

    kwds = {"bar": "bar", "biz": "biz", "baz": "baz"}

    match_params(foo, kwds) -> {"bar": "bar", "biz": "biz"}
    match_params(bar, kwds) -> {"bar": "bar", "biz": "biz", "baz": "baz"}
    """
    params = inspect.signature(func).parameters
    variadic = any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in params.values()
    )
    matched = {}
    if variadic:
        matched.update(kwargs)
    else:
        for name, value in kwargs.items():
            param = params.get(name)
            if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
                matched[name] = value
    return matched


def get(obj: Any, attrs: str, default: Any = MISSING) -> Any:
    match = re.match("(?P<attr>\\w+)?(\\[(?P<item>.+)])?", attrs)
    if match is None:
        raise ValueError("invalid sole combined getattr attribute indicator")
    attr, item = match.group("attr"), match.groupdict().get("item")
    got = getattr(obj, attr)
    if item:
        if got is default:
            if got is MISSING:
                raise AttributeError(got)
        try:
            got_item = got[item]
        except (LookupError, AttributeError):
            if default is MISSING:
                raise
            got_item = default
    else:
        got_item = default
        if got_item is MISSING:
            raise KeyError(got)
    return got_item


def get_attrs(obj: Any, attrs: str, default: Any = MISSING) -> Any:
    *path, end = attrs.split(".")
    trailing = obj
    if path:
        trailing = functools.reduce(functools.partial(get), path, obj)
    got = get(trailing, end, default)
    if got is MISSING:
        raise AttributeError(type(obj).__name__ + "." + attrs)
    return got
