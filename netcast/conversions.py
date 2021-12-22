from __future__ import annotations

import dataclasses
import operator
from typing import Any, Hashable, Callable, TypeVar, Sequence


def coerce_var(v):
    if isinstance(v, _BaseVar):
        return v
    return Var(v)


TT = TypeVar('TT', Callable[[Any, Any], Any], type(None))


@dataclasses.dataclass
class Replacement:
    from_value: _BaseVar
    to_value: _BaseVar
    key: KT = operator.eq

    def __iter__(self):
        return dataclasses.fields(self)

    def __new__(cls, *args, **kwargs):
        if args:
            maybe_replacement = args[0]
            if isinstance(maybe_replacement, Replacement):
                return maybe_replacement
        return object.__new__(cls)

    @classmethod
    def from_multiple_replacements(
            cls, *replacements: (
                Sequence[_BaseVar, _BaseVar]
                | Sequence[_BaseVar, _BaseVar, KT]
                | Replacement
            )
    ):
        return tuple(map(lambda r: (cls, lambda *_: r)[isinstance(r, cls)](*r), replacements))


class _BaseVar:
    _replacement_class = Replacement

    def __neg__(self):
        """Used for left-arrow notation."""
        return self

    def __lt__(self, other):
        """Used for left-arrow notation."""
        return self._replacement_class(coerce_var(other), self)


@dataclasses.dataclass
class Var(_BaseVar):
    value: Hashable
    transformer: TT = None


@dataclasses.dataclass
class MemoryVar(_BaseVar):
    value: Any
    transformer = id


KT = Callable[[_BaseVar, _BaseVar], bool]
