from __future__ import annotations

import abc
import copy
import enum
from typing import Any, ClassVar, Generic, TypeVar, final, Type

from netcast import RootedTreeContextMixin, Context
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


class Constraint(Generic[Origin, Cast], metaclass=abc.ABCMeta):
    def __init__(self, policy: ConstraintPolicy, **cfg):
        self._cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.policy = policy

    @staticmethod
    def is_origin_ok(obj: Origin):
        return obj or True

    @staticmethod
    def is_cast_ok(obj: Cast):
        return obj or True

    @staticmethod
    def reshape_origin(obj: Origin):
        """Reshape a value to suppress the errors."""
        return obj

    @staticmethod
    def reshape_cast(obj: Cast):
        """Reshape a value to suppress the errors."""
        return obj

    def validate(self, obj: Origin | Cast, origin: bool = False):
        """Validate an object and return it."""
        is_ok = self.is_origin_ok(obj) if origin else self.is_cast_ok(obj)
        if self.policy is ConstraintPolicy.ignore or is_ok:
            return obj
        if self.policy is ConstraintPolicy.reshape:
            return self.reshape_origin(obj) if origin else self.reshape_cast(obj)
        raise ConstraintError(''.join(getattr(self, 'error_msg', ())))


class DataTypeRegistry(RootedTreeContextMixin, AttributeDict):
    """Data types registry."""


class TypeArrangement(ClassArrangement, config=True):
    __type_key__: Any = None
    __origin_type__: Any = None

    context_class: Type[Context] = DataTypeRegistry

    @final
    @classmethod
    def subcontext_key(cls, *__related_contexts):
        """Return the key for all the subcontexts."""
        if cls.__type_key__ == getattr(cls.__base__, '__type_key__', None):
            orig_type = cls.__origin_type__
            if orig_type is not None:
                cls.__type_key__ = orig_type
        return cls.__type_key__


class DataType(TypeArrangement, metaclass=abc.ABCMeta):
    constraints: ClassVar[tuple[Constraint[Origin, Cast], ...]] = ()

    def __init__(self, **cfg: Any):
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)

    def __init_subclass__(cls, **kwargs):
        if cls.__base__ is not DataType and cls.new_context is None:
            cls.new_context = True
        super().__init_subclass__(**kwargs)

    def copy(self, deep=False, **cfg: Any) -> DataType:  # [Origin, Cast]:
        """Copy this type."""
        if deep:
            new_cfg = {**copy.deepcopy(self.cfg), **cfg}
        else:
            new_cfg = self.cfg
            new_cfg.update(cfg)
        new = type(self)(**new_cfg)
        new.constraints = (copy.deepcopy(self.constraints) if deep else self.constraints)
        return new

    @abc.abstractmethod
    def _cast(self, orig_value: Origin) -> Cast:
        raise NotImplementedError

    def cast(self, orig_value: Origin) -> Cast:
        """Cast an origin value to the cast type."""
        for constraint in self.constraints:
            orig_value = constraint.validate(orig_value, origin=True)
        cast_value = self._cast(orig_value)
        for constraint in self.constraints:
            cast_value = constraint.validate(cast_value)
        return cast_value

    def __call__(self, **cfg: Any) -> DataType:  # [Origin, Cast]:
        return self.copy(**cfg)
