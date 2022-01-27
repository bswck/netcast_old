from __future__ import annotations

import abc
import copy
import enum
from typing import Any, ClassVar, Generic, TypeVar, final, Type

from netcast import ClassArrangement, Context, DoublyLinkedListContextMixin
from netcast.toolkit.collections import AttributeDict

Load = TypeVar('Load')
Dump = TypeVar('Dump')


class ConstraintPolicy(enum.Enum):
    ignore = 'ignore'
    reshape = 'reshape'
    strict = 'strict'


class ConstraintError(ValueError):
    """A constraint failed."""


class Constraint(Generic[Load, Dump], metaclass=abc.ABCMeta):
    def __init__(self, policy: ConstraintPolicy, **cfg):
        self._cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.policy = policy

    @staticmethod
    def validate_load(obj: Load):
        return obj or True

    @staticmethod
    def reshape_load(obj: Load):
        """Reshape a value to suppress the errors."""
        return obj

    @staticmethod
    def validate_dump(obj: Dump):
        return obj or True

    @staticmethod
    def reshape_dump(obj: Dump):
        """Reshape a value to suppress the errors."""
        return obj

    def validate(self, obj: Load | Dump, **dump_or_load):
        """Validate an object and return it."""
        if len(set(dump_or_load).intersection(('load', 'dump'))) != 1:
            raise ValueError('load=True xor dump=True must be set')
        load = dump_or_load.get('load', False)
        is_ok = self.validate_load(obj) if load else self.validate_dump(obj)
        if self.policy is ConstraintPolicy.ignore or is_ok:
            return obj
        if self.policy is ConstraintPolicy.reshape:
            return self.reshape_load(obj) if load else self.reshape_dump(obj)
        raise ConstraintError(''.join(getattr(self, 'error_msg', ())))


class DataTypeRegistry(DoublyLinkedListContextMixin, AttributeDict):
    """Data types registry."""


class TypeArrangement(ClassArrangement, config=True):
    __type_key__: Any = None
    __origin_type__: Any = None

    context_class: Type[Context] = DataTypeRegistry

    @classmethod
    @final
    def subcontext_key(cls, *__related_contexts):
        """Return the key for all the subcontexts."""
        if cls.__type_key__ == getattr(cls.__base__, '__type_key__', None):
            orig_type = cls.__origin_type__
            if orig_type is not None:
                cls.__type_key__ = orig_type
        return cls.__type_key__


class DataType(TypeArrangement, metaclass=abc.ABCMeta):
    constraints: ClassVar[tuple[Constraint[Load, Dump], ...]] = ()

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
    def _dump(self, load: Load) -> Dump:
        raise NotImplementedError

    @abc.abstractmethod
    def _load(self, dump: Dump) -> Load:
        raise NotImplementedError

    def dump(self, load: Load) -> Dump:
        """Cast an origin value to the cast type."""
        for constraint in self.constraints:
            load = constraint.validate(load, load=True)
        dump = self._dump(load)
        for constraint in self.constraints:
            dump = constraint.validate(dump, dump=True)
        return dump

    def load(self, dump: Dump) -> Load:
        """Cast an origin value to the cast type."""
        for constraint in self.constraints:
            dump = constraint.validate(dump, dump=True)
        load = self._load(dump)
        for constraint in self.constraints:
            load = constraint.validate(load, load=True)
        return load

    def __call__(self, **cfg: Any) -> DataType:  # [Origin, Cast]:
        return self.copy(**cfg)
