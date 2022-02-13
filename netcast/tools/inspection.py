import inspect


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
