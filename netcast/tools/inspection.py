def is_classmethod(cls, method):
    return getattr(method, "__self__", None) is cls
