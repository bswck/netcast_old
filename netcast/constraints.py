from __future__ import annotations

import abc
import enum
import functools
from typing import Literal, Any, TYPE_CHECKING

from netcast.exceptions import ConstraintError
from netcast.tools import AttributeDict
from netcast.tools import strings

if TYPE_CHECKING:
    Policies = Literal["ignore", "shape", "strict"]


class ConstraintPolicy(enum.Enum):
    IGNORE = "ignore"
    SHAPE = "shape"
    STRICT = "strict"

    _value2member_map_: dict[str, ConstraintPolicy]  # pylint: disable=C0103


class Constraint(metaclass=abc.ABCMeta):
    _policy = "strict"

    def __init__(self, policy: Policies | ConstraintPolicy = _policy, **cfg: Any):
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
    def shape_dump(cls, obj):
        return obj

    @classmethod
    def shape_load(cls, obj):
        return obj

    @property
    def policy(self):
        return self._policy

    @policy.setter
    def policy(self, policy):
        if isinstance(policy, str):
            valid_opts = ConstraintPolicy._value2member_map_
            if policy not in valid_opts:
                raise ValueError(f"invalid constraint policy: {policy!r}")
            policy = valid_opts[policy]
        self._policy = policy

    def call_validate(self, obj, load=False, dump=False):
        if load and not dump:
            validate = self.validate_load
        elif dump and not load:
            validate = self.validate_dump
        else:
            raise ValueError("only one of 'load' and 'dump' parameters must be set to True")
        try:
            validate(obj)
        except AssertionError as err:
            raise ConstraintError(f'constraint failed: {err}') from err

    def call_shape(self, obj, load=False, dump=False):
        if load and not dump:
            shape = self.shape_load
        elif dump and not load:
            shape = self.shape_dump
        else:
            raise ValueError("only one of 'load' and 'dump' parameters must be set to True")
        try:
            obj = shape(obj)
        except Exception as err:
            raise ConstraintError(f'calling shape failed: {err}') from err
        return obj

    def validate(self, obj, *, load=False, dump=False):
        """Validate an object and return it."""
        try:
            self.call_validate(obj, load=load, dump=dump)
        except ConstraintError:
            if self.policy is ConstraintPolicy.STRICT:
                raise
            if self.policy is ConstraintPolicy.SHAPE:
                obj = self.call_shape(obj, load=load, dump=dump)
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

    def shape_load(self, load):
        if load < self.min:
            return self.min
        return self.max
