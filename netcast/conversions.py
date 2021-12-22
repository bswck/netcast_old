from __future__ import annotations

import dataclasses
import operator
from typing import Any, Hashable, Callable, TypeVar


def coerce_var(v):
    if isinstance(v, Var):
        return v
    return Var(v)


TT = TypeVar('TT', Callable[[Any, Any], Any], type(None))


@dataclasses.dataclass
class Var:
    value: Hashable
    transformer: TT = None
    metadata: dict | None = None

    def __neg__(self):
        return self

    def __lt__(self, other):
        return Replacement(coerce_var(other), self)


@dataclasses.dataclass
class Replacement:
    from_value: Var
    to_value: Var
    key: Callable[[Var, Var], bool] = operator.eq
