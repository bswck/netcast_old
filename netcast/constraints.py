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
        pass

    @classmethod
    def validate_load(cls, obj):
        pass

    @classmethod
    def reshape_dump(cls, obj):
        return obj

    @classmethod
    def reshape_load(cls, obj):
        return obj

    def validate(self, obj, **dump_or_load):
        """Validate an object and return it."""
        if len(set(dump_or_load).intersection(("load", "dump"))) != 1:
            raise ValueError("load=True or dump=True must be set")

        load = dump_or_load.get("load", False)

        if load:
            validate = self.validate_load
        else:
            validate = self.validate_dump

        try:
            try:
                validate(obj)
            except AssertionError as err:
                raise ConstraintError(f'constraint failed: {err}') from err

        except ConstraintError:
            if self.policy is ConstraintPolicy.STRICT:
                raise
            if self.policy is ConstraintPolicy.RESHAPE:
                obj = self.reshape_load(obj) if load else self.reshape_dump(obj)

        return obj

    def __getattr__(self, item):
        return getattr(self.cfg, item)


class InstanceConstraint(Constraint):
    def setup(self):
        self.setdefault('load_type', object)
        self.setdefault('dump_type', object)

    def validate_load(self, load):
        msg = f'loaded object must be an instance of {self.cfg.load_type.__name__}'
        assert isinstance(load, self.load_type), msg

    def validate_dump(self, dump):
        msg = f'dumped object must be an instance of {self.cfg.dump_type.__name__}'
        assert isinstance(dump, self.dump_type), msg


class RangeConstraint(Constraint):
    def setup(self):
        if self.min > self.max:
            raise ValueError("the minimal value cannot be less than the maximal value")
        self.setdefault("accept_inf", False)

    def validate_load(self, load):
        minimal, maximal = self.min, self.max
        accept_inf = self.accept_inf

        bounded = minimal <= load <= maximal or accept_inf

        if bounded:
            return

        minimal, maximal = map(
            functools.partial(strings.truncate, stats=None),
            map(str, (minimal, maximal)),
        )
        msg = f"loaded object is out of bounds [{minimal}, {maximal}]"
        assert bounded, msg

    def reshape_load(self, load):
        if load < self.min:
            return self.min
        return self.max
