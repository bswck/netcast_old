import functools
import inspect
import re

from netcast.constants import MISSING
from netcast.tools import strings


def is_classmethod(cls, method):
    return getattr(method, "__self__", None) is cls


def adjust_kwargs(func, kwargs):
    adapted = {}
    parameters = inspect.signature(func).parameters
    is_variadic = any(param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters.values())
    if is_variadic:
        adapted.update(kwargs)
    else:
        for name, value in kwargs.items():
            param = parameters.get(name)
            if param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
                adapted[name] = value
    return adapted


def get_sole_combined_attr(obj, combined_attr, default=MISSING):
    match = re.match("(?P<attr>\\w+)(\\[(?P<item>\\w+)])?", combined_attr)
    if match is None:
        raise ValueError("invalid sole combined getattr attribute indicator")
    attr, item = match.group("attr"), match.groupdict().get("item")
    accessed_attr = getattr(obj, attr, default)
    if item:
        if item.startswith('"') and item.endswith('"'):
            item = strings.trim(item, '"')
        elif item.startswith("'") and item.endswith("'"):
            item = strings.trim(item, "'")
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
    last = functools.reduce(functools.partial(get_sole_combined_attr), path, obj)
    ret = get_sole_combined_attr(last, end, default)
    if ret is MISSING:
        raise AttributeError(type(obj).__name__ + "." + combined_attr)
    return ret
