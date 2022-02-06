from __future__ import annotations

import abc
import enum
import functools
from typing import Literal, Any, TYPE_CHECKING

from netcast.exceptions import ConstraintError
from netcast.tools import AttributeDict
from netcast.tools import strings

if TYPE_CHECKING:
    Policies = Literal["ignore", "reshape", "strict"]


class ConstraintPolicy(enum.Enum):
    IGNORE = "ignore"
    RESHAPE = "reshape"
    STRICT = "strict"

    _value2member_map_: dict[str, ConstraintPolicy]  # pylint: disable=C0103


class Constraint(metaclass=abc.ABCMeta):
    def __init__(self, policy: Policies | ConstraintPolicy = "strict", **cfg: Any):
        if isinstance(policy, str):
            valid_opts = ConstraintPolicy._value2member_map_
            if policy not in valid_opts:
                raise ValueError(f"invalid constraint policy: {policy!r}")
            policy = valid_opts[policy]
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.policy = policy
        self.setup()

    def setup(self):
        """Constraint setup."""

    @classmethod
    def validate_dump(cls, obj):
        return obj or True

    @classmethod
    def validate_load(cls, obj):
        return True

    @classmethod
    def reshape_load(cls, obj):
        return obj

    @classmethod
    def reshape_dump(cls, obj):
        return obj

    def validate(self, obj, **dump_or_load):
        """Validate an object and return it."""
        if len(set(dump_or_load).intersection(("load", "dump"))) != 1:
            raise ValueError("load=True or dump=True must be set")

        load = dump_or_load.get("load", False)

        try:
            validate = (self.validate_dump, self.validate_load)[load]
            validate(obj)

        except ConstraintError:
            if self.policy is ConstraintPolicy.STRICT:
                raise
            if self.policy is ConstraintPolicy.RESHAPE:
                obj = self.reshape_load(obj) if load else self.reshape_dump(obj)
        return obj


class RangeConstraint(Constraint):
    def setup(self):
        if self.cfg.min > self.cfg.max:
            raise ValueError("the minimal value cannot be less than the maximal value")
        self.cfg.setdefault("allow_inf", False)

    def validate_load(self, load):
        min_val, max_val = self.cfg.min, self.cfg.max
        allow_inf = self.cfg.allow_inf

        if min_val <= load <= max_val or allow_inf:
            return load

        min_val, max_val = map(
            functools.partial(strings.truncate, stats=None),
            map(str, (min_val, max_val)),
        )
        raise ConstraintError(
            f"loaded object is out of serialization bounds [{min_val}, {max_val}]"
        )

    def reshape_load(self, load):
        if load < self.cfg.min:
            return self.cfg.min
        return self.cfg.max
