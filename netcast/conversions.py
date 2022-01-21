from __future__ import annotations

import dataclasses
import operator
from typing import Any, Hashable, Callable
try:
    from types import NoneType
except ImportError:
    NoneType = type(None)


def coerce_var(v):
    if isinstance(v, _BaseVar):
        return v
    return Key(v)


KT = Callable[[Any, Any], bool]  # Key type


@dataclasses.dataclass
class Replacement:
    old_value: _BaseVar
    new_value: _BaseVar
    key: KT = operator.eq

    def __iter__(self):
        return dataclasses.fields(self)

    def __post_init__(self):
        self.check_possible()

    def __new__(cls, *args, **kwargs):
        if args:
            maybe_replacement = args[0]
            if isinstance(maybe_replacement, Replacement):
                return maybe_replacement
        return object.__new__(cls)

    def check_possible(self):
        if not isinstance(self.old_value, type(self.new_value)):
            raise TypeError("types of replacement arguments do not match")
        assert self.old_value.replaceable(self.new_value), "old value isn't replaceable"
        assert self.new_value.applicable(self.old_value), "new value isn't applicable"

    @classmethod
    def from_multiple_replacements(cls, *replacements: Replacement):
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

    def applicable_itself(self):
        return True

    def replaceable_itself(self):
        return True

    def replaceable(self, to_value):
        return self.replaceable_itself() or not to_value.replaceable_itself()

    def applicable(self, from_value):
        return self.applicable_itself() or not from_value.applicable_itself()

    def __neg__(self):
        """Used for left-arrow notation."""
        return self

    def __lt__(self, other):
        """Used for left-arrow notation."""
        return self._replacement_class(coerce_var(other), self)


@dataclasses.dataclass
class Key(_BaseVar):
    value: Hashable

    def applicable_itself(self):
        try:
            hash(self.value)
        except TypeError:
            return False
        else:
            return True


@dataclasses.dataclass
class Value(_BaseVar):
    value: Any
