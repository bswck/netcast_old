from __future__ import annotations

import abc
import enum
import functools
import numbers
from typing import Literal, Any, TYPE_CHECKING

from netcast.exceptions import ConstraintError
from netcast.tools import AttributeDict
from netcast.tools import strings

if TYPE_CHECKING:
    Policies = Literal["ignore", "coerce", "strict"]


class ConstraintPolicy(enum.Enum):
    IGNORE = "ignore"
    SHAPE = "coerce"
    STRICT = "strict"

    _value2member_map_: dict[str, ConstraintPolicy]  # pylint: disable=C0103


class Constraint(metaclass=abc.ABCMeta):
    _policy = "strict"

    def __init__(self, policy: Policies | ConstraintPolicy = _policy, **cfg: Any):
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.setdefault('serializer_cfg', AttributeDict())
        self.policy = policy
        self.setup()

    def setup(self):
        """Constraint setup."""

    def validate_dump(self, obj):
        pass

    def validate_load(self, obj):
        pass

    def coerce_dump(self, obj):
        return NotImplemented

    def coerce_load(self, obj):
        return NotImplemented

    def notify(self, serializer):
        # We won't link to serializer here, because we don't want
        # to create a strong reference to it.
        cfg = serializer.cfg.copy()
        self.policy = cfg.pop('constraint_policy')
        self.cfg.update(serializer_cfg=cfg)

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

    def call_coerce(self, obj, load=False, dump=False):
        if load and not dump:
            cast = self.coerce_load
        elif dump and not load:
            cast = self.coerce_dump
        else:
            raise ValueError("only one of 'load' and 'dump' parameters must be set to True")
        try:
            obj = cast(obj)
        except Exception as err:
            raise ConstraintError(f'calling cast failed: {err}') from err
        else:
            if obj is NotImplemented:
                raise NotImplementedError(f'cannot coerce that the object has the desired shape')
        return obj

    def validate(self, obj, *, load=False, dump=False):
        """Validate an object and return it."""
        try:
            self.call_validate(obj, load=load, dump=dump)
        except ConstraintError:
            if self.policy is ConstraintPolicy.STRICT:
                raise
            if self.policy is ConstraintPolicy.SHAPE:
                obj = self.call_coerce(obj, load=load, dump=dump)
        return obj

    def __getattr__(self, item):
        return getattr(self.cfg, item)


class InstanceConstraint(Constraint):
    def setup(self):
        self.setdefault('load_type', object)
        self.setdefault('dump_type', object)

    @staticmethod
    def _get_type_name(typ):
        if isinstance(typ, tuple):
            type_name = ", ".join(map(lambda typ_: typ_.__name__, typ))
            type_name = type_name[::-1].replace(" ,", "ro", 1)[::-1]  # fixme
        else:
            type_name = typ.__name__
        return type_name

    def validate_load(self, load):
        msg = f"loaded object must be an instance of {self._get_type_name(self.load_type)}"
        assert isinstance(load, self.load_type), msg

    def validate_dump(self, dump):
        msg = f"dumped object must be an instance of {self._get_type_name(self.dump_type)}"
        assert isinstance(dump, self.dump_type), msg

    def coerce_numeric(self, obj, desired_type):
        obj_type = type(obj)
        if desired_type is int and obj_type is float:
            return int(obj)
        if desired_type is float and obj_type is int:
            return float(obj)
        return NotImplemented

    def coerce_string(self, obj, desired_type):
        obj_type = type(obj)
        encoding = self.get('encoding', 'ascii')
        if desired_type is bytes and obj_type is str:
            return obj.encode(encoding)
        if desired_type is str and obj_type is bytes:
            return obj.decode(encoding)
        return NotImplemented

    def coerce_load(self, load):
        load_type = type(load)
        if issubclass(load_type, numbers.Number):
            return self.coerce_numeric(load, self.load_type)
        if issubclass(load_type, (str, bytes)):
            return self.coerce_string(load, self.load_type)
        return NotImplemented


class RangeConstraint(Constraint):
    def setup(self):
        if self.min > self.max:
            raise ValueError("the minimal value cannot be less than the maximal value")
        self.setdefault("accept_inf", False)

    def validate_load(self, load):
        minimal, maximal = self.min, self.max
        accept_inf = self.accept_inf

        bounded = (minimal <= load <= maximal) or accept_inf

        if bounded:
            return

        minimal, maximal = map(
            functools.partial(strings.truncate, stats=None),
            map(str, (minimal, maximal)),
        )
        msg = f"loaded object is out of bounds [{minimal}, {maximal}]"
        assert bounded, msg

    def coerce_load(self, load):
        if load < self.min:
            return self.min
        if load > self.max:
            return self.max
        return load
