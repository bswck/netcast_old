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


def getattr_or_getitem(obj, attrs, default=MISSING):
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


def get_attrs(obj, attrs, default=MISSING):
    *path, end = attrs.split(".")
    trailing = obj
    if path:
        trailing = functools.reduce(functools.partial(getattr_or_getitem), path, obj)
    got = getattr_or_getitem(trailing, end, default)
    if got is MISSING:
        raise AttributeError(type(obj).__name__ + "." + attrs)
    return got
