import functools
import inspect
import re

from netcast.constants import MISSING


def is_classmethod(cls, method):
    return getattr(method, "__self__", None) is cls


def force_compliant_kwargs(func, kwargs):
    """
    def foo(baz, /, bar, biz):
        pass

    def bar(foo, **baz):
        pass

    kwds = {"bar": "bar", "biz": "biz", "baz": "baz"}

    force_compliant_kwargs(foo, kwds) -> {"bar": "bar", "biz": "biz"}
    force_compliant_kwargs(bar, kwds) -> {"bar": "bar", "biz": "biz", "baz": "baz"}
    """
    adj = {}
    pms = inspect.signature(func).parameters
    var = any(param.kind is inspect.Parameter.VAR_KEYWORD for param in pms.values())
    if var:
        adj.update(kwargs)
    else:
        for name, value in kwargs.items():
            param = pms.get(name)
            if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
                adj[name] = value
    return adj


def onefold_combined_getattr(obj, combined_attr, default=MISSING):
    match = re.match("(?P<attr>\\w+)?(\\[(?P<item>.+)])?", combined_attr)
    if match is None:
        raise ValueError("invalid sole combined getattr attribute indicator")
    attr, item = match.group("attr"), match.groupdict().get("item")
    accessed_attr = getattr(obj, attr, default)
    if item:
        if item.startswith('"') or item.startswith("'"):
            item = item[1:-1]
        if accessed_attr is default:
            if accessed_attr is MISSING:
                raise AttributeError(accessed_attr)
        try:
            accessed_item = accessed_attr[item]
        except (LookupError, AttributeError):
            if default is MISSING:
                raise
            accessed_item = default
    else:
        accessed_item = default
        if accessed_item is MISSING:
            raise KeyError(accessed_attr)
    return accessed_item


def combined_getattr(obj, combined_attr, default=MISSING):
    *path, end = combined_attr.split(".")
    if path:
        trailing = functools.reduce(
            functools.partial(onefold_combined_getattr), path, obj
        )
    else:
        trailing = obj
    result = onefold_combined_getattr(trailing, end, default)
    if result is MISSING:
        raise AttributeError(type(obj).__name__ + "." + combined_attr)
    return result
