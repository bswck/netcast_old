from netcast.tools.symbol import Symbol

__all__ = ("MISSING", "GREATEST", "LEAST")

MISSING = Symbol("missing")


class _Greatest:
    __lt__ = __le__ = staticmethod(lambda _: False)
    __gt__ = __ge__ = staticmethod(lambda _: True)


class _Least:
    __lt__ = __le__ = staticmethod(lambda _: True)
    __gt__ = __ge__ = staticmethod(lambda _: False)


GREATEST = _Greatest()
LEAST = _Least()
