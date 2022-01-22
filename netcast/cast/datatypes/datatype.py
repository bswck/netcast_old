from __future__ import annotations

import abc
import enum
from typing import Any, Type

from netcast.toolkit.collections import AttributeDict
from netcast.arrangements import DArrangement


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


class DataType:
    def __init__(self, **cfg: [str, Any]):
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.constraints: tuple[Constraint, ...] = ()

    def copy(self, **cfg: [str, Any]):
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
    def python_type(self) -> type:
        """Get a Python type that this Type object refers to."""
        python_type = object
        return python_type

    @abc.abstractmethod
    @property
    def template_type(self) -> Type[Template]:
        """Get a template type that this Type object refers to."""
        template_type = Template
        return template_type

    @abc.abstractmethod
    def create_template(self) -> Template:
        """Create a type template."""

    def __call__(self, **cfg):
        return self.copy(**cfg)


class Template(DArrangement, metaclass=abc.ABCMeta):
    def __init__(self, descent, data_type: DataType):
        super().__init__(descent)
        self.type = data_type

    @abc.abstractmethod
    @property
    def source(self) -> Any:
        """Template source."""
        return Any

    @abc.abstractmethod
    def cast(self, val):
        """Get a value cast to the template type."""
        return val

    def save(self):
        """Optional. Used for file-based templates."""

    def process(self, python_value):
        for constraint in self.type.constraints:
            python_value = constraint.validate(python_value, python=True)
        cast_value = self.cast(python_value)
        for constraint in self.type.constraints:
            cast_value = constraint.validate(cast_value)
        return cast_value
