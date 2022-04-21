from netcast.tools.symbol import Symbol


__all__ = ("MISSING", "GREATEST", "LEAST")


class _Greatest:
    __lt__ = __le__ = staticmethod(lambda _: False)
    __gt__ = __ge__ = staticmethod(lambda _: True)


class _Least:
    __lt__ = __le__ = staticmethod(lambda _: True)
    __gt__ = __ge__ = staticmethod(lambda _: False)


MISSING: Symbol = Symbol("MISSING")
GREATEST: _Greatest = _Greatest()
LEAST: _Least = _Least()
