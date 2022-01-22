from __future__ import annotations

import dataclasses
import operator
from typing import Any, Hashable, Callable


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
            raise TypeError('types of replacement arguments do not match')
        assert self.old_value.replaceable(self.new_value), 'old value isn\'t replaceable'
        assert self.new_value.applicable(self.old_value), 'new value isn\'t applicable'

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


@dataclasses.dataclass
class _LeftArrowMark:
    obj: Any


class _BaseVar:
    value: Any
    _cached_mark = None

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
        if self._cached_mark is None:
            self._cached_mark = _LeftArrowMark(self)
        return self._cached_mark

    def __lt__(self, other):
        """Used for left-arrow notation."""
        if isinstance(other, _LeftArrowMark):
            return Replacement(other, self)
        try:
            return self.value.__lt__(other)
        except AttributeError:
            return NotImplemented


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
