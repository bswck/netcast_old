from __future__ import annotations

import dataclasses
import operator
from typing import Any, Hashable, Callable, TypeVar, Sequence
try:
    from types import NoneType
except ImportError:
    NoneType = type(None)


def coerce_var(v):
    if isinstance(v, _BaseVar):
        return v
    return Key(v)


KT = Callable[[Any, Any], bool]  # Key type
TT = TypeVar('TT', Callable[[Any, Any], Any], NoneType)  # Transformer type


@dataclasses.dataclass
class Replacement:
    from_value: _BaseVar
    to_value: _BaseVar
    key: KT = operator.eq

    def __iter__(self):
        return dataclasses.fields(self)

    def __post_init__(self):
        self.check_replaceable()

    def __new__(cls, *args, **kwargs):
        if args:
            maybe_replacement = args[0]
            if isinstance(maybe_replacement, Replacement):
                return maybe_replacement
        return object.__new__(cls)

    def check_replaceable(self):
        if not isinstance(self.from_value, type(self.to_value)):
            raise TypeError("types of replacement arguments do not match")
        assert self.from_value.replaceable(), "from_value isn't replaceable"
        assert self.to_value.applicable(self.from_value), "to_value isn't replaceable"

    @classmethod
    def from_multiple_replacements(
            cls, *replacements: (
                Sequence[_BaseVar, _BaseVar]
                | Replacement
            )
    ):
        self = tuple(map(
            lambda replacement: (
                lambda: cls(*replacement),
                lambda: replacement
            )[isinstance(replacement, cls)](),
            replacements
        ))
        return self


class _BaseVar:
    value: Any
    _replacement_class = Replacement

    def replaceable(self):
        return True

    def applicable(self):
        return True

    def __neg__(self):
        """Used for left-arrow notation."""
        return self

    def __lt__(self, other):
        """Used for left-arrow notation."""
        return self._replacement_class(coerce_var(other), self)


@dataclasses.dataclass
class Key(_BaseVar):
    value: Hashable
    transformer: TT = hash

    def applicable(self):
        try:
            hash(self.value)
        except TypeError:
            return False
        else:
            return True


@dataclasses.dataclass
class Value(_BaseVar):
    value: Any
    transformer: TT = None
