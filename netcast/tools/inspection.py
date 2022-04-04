from __future__ import annotations  # Python 3.8

import inspect
from typing import Any, Callable


def is_classmethod(cls: type, method: Callable) -> bool:
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
            if param is None:
                continue
            if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
                matched[name] = value
    return matched
