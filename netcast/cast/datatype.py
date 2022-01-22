from __future__ import annotations

import abc
import enum
from typing import Any, ClassVar, Generic, TypeVar

from netcast import RootedTreeContextMixin
from netcast.toolkit.collections import AttributeDict
from netcast.arrangements import ClassArrangement

Origin = TypeVar('Origin')
Cast = TypeVar('Cast')


class ConstraintPolicy(enum.Enum):
    ignore = 'ignore'
    reshape = 'reshape'
    strict = 'strict'


class ConstraintError(ValueError):
    """A constraint failed."""


class Constraint(metaclass=abc.ABCMeta):
    def __init__(self, policy: ConstraintPolicy, **cfg):
        self._cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.policy = policy

    @staticmethod
    def is_ok_python(obj: Any):
        return obj

    @staticmethod
    def is_ok(obj: Any):
        return obj

    @staticmethod
    def reshape_python(obj: Any):
        """Reshape a value to suppress the errors."""
        return obj

    @staticmethod
    def reshape(obj: Any):
        """Reshape a value to suppress the errors."""
        return obj

    def validate(self, obj: Any, python=False):
        """Validate an object and return it."""
        is_ok = self.is_ok_python(obj) if python else self.is_ok(obj)
        if self.policy is ConstraintPolicy.ignore or is_ok:
            return obj
        if self.policy is ConstraintPolicy.reshape:
            return self.reshape_python(obj) if python else self.reshape(obj)
        raise ConstraintError(''.join(getattr(self, 'error_msg', ())))


class DataTypeRegistry(RootedTreeContextMixin, AttributeDict):
    """Data types registry."""


class TypeArrangement(ClassArrangement, family=True):
    context_class = DataTypeRegistry


class DataType(TypeArrangement, Generic[Origin, Cast], irregular=True, metaclass=abc.ABCMeta):
    constraints: ClassVar[tuple[Constraint, ...]] = ()

    def __init__(self, **cfg: Any):
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)

    def copy(self, **cfg: Any) -> DataType[Origin, Cast]:
        """Copy this type."""
        if cfg:
            new_cfg = {**self.cfg, **cfg}
        else:
            new_cfg = self.cfg
        new = type(self)(**new_cfg)
        new.constraints = self.constraints
        return new

    @abc.abstractmethod
    @property
    def type_key(self):
        raise NotImplementedError

    @abc.abstractmethod
    @property
    def python_type(self) -> Origin:
        """Get an origin Python type that this Type object refers to."""
        python_type = object
        return python_type

    @abc.abstractmethod
    def _cast(self, python_value: Origin) -> Cast:
        new_value = python_value
        return new_value

    def cast(self, python_value: Origin) -> Cast:
        """Create a type template."""
        for constraint in self.constraints:
            python_value = constraint.validate(python_value, python=True)
        cast_value = self._cast(python_value)
        for constraint in self.constraints:
            cast_value = constraint.validate(cast_value)
        return cast_value

    def __call__(self, **cfg: Any) -> DataType[Origin, Cast]:
        return self.copy(**cfg)
