from __future__ import annotations

import abc
import copy
import enum
from typing import Any, ClassVar, Generic, TypeVar, final, Type, Literal

from netcast import ClassArrangement, Context, DoublyLinkedListContextMixin
from netcast.toolkit.collections import AttributeDict

Load = TypeVar('Load')
Dump = TypeVar('Dump')


class ConstraintPolicy(enum.Enum):
    ignore = 'ignore'
    reshape = 'reshape'
    strict = 'strict'


_Policies = Literal['ignore', 'reshape', 'strict']


class ConstraintError(ValueError):
    """A constraint failed."""


class Constraint(Generic[Load, Dump], metaclass=abc.ABCMeta):
    def __init__(self, policy: _Policies | ConstraintPolicy | None = 'strict', **cfg: Any):
        if isinstance(policy, str):
            valid_opts = ConstraintPolicy._value2member_map_
            if policy not in valid_opts:
                raise ValueError(f'invalid constraint policy: {policy!r}')
            policy = valid_opts[policy]
        elif policy is None:
            policy = ConstraintPolicy.strict
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.policy = policy

    @staticmethod
    def _validate_default(obj: Load | Dump):
        return obj or True

    validate_dump = _validate_default
    validate_load = _validate_default

    @staticmethod
    def _reshape_default(obj: Load | Dump):
        return obj

    reshape_load = _reshape_default
    reshape_dump = _reshape_default

    def validate(self, obj: Load | Dump, **dump_xor_load):
        """Validate an object and return it."""
        if len(set(dump_xor_load).intersection(('load', 'dump'))) != 1:
            raise ValueError('load=True xor dump=True must be set')
        load = dump_xor_load.get('load', False)
        try:
            validate = (self.validate_dump, self.validate_load)[load]
            validate(obj)
        except ConstraintError:
            if self.policy is ConstraintPolicy.ignore:
                return obj
            if self.policy is ConstraintPolicy.reshape:
                return self.reshape_load(obj) if load else self.reshape_dump(obj)
            raise


class DataTypeRegistry(DoublyLinkedListContextMixin, AttributeDict):
    """Data types registry."""


class TypeArrangement(ClassArrangement, config=True):
    __visit_key__: Any = None
    __load_type__: Any = None

    context_class: Type[Context] = DataTypeRegistry

    def preprocess_context(self, context):
        context.me = self
        if type(self) is not TypeArrangement:
            context.category = self.__base__.subcontext_key()  # type: ignore
        return context

    @classmethod
    @final
    def subcontext_key(cls, *__related_contexts):
        """Return the key for all the subcontexts."""
        if cls.__visit_key__ == getattr(cls.__base__, '__visit_key__', None):
            orig_type = cls.__load_type__
            if orig_type is not None:
                cls.__visit_key__ = orig_type
        return cls.__visit_key__


class Serializer(TypeArrangement, metaclass=abc.ABCMeta):
    """A base class for all serializers. A good serializer can dump and load stuff."""

    constraints: ClassVar[tuple[Constraint[Load, Dump], ...]] = ()

    def __init__(self, **cfg: Any):
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)

    def __init_subclass__(cls, **kwargs):
        """A subclass hook for DRY."""
        if cls.__base__ is not Serializer and cls.new_context is None:
            cls.new_context = True
        super().__init_subclass__(**kwargs)

    def copy(self, deep=False, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        """Copy this type."""
        if deep:
            new_cfg = {**copy.deepcopy(self.cfg), **cfg}
        else:
            new_cfg = self.cfg
            new_cfg.update(cfg)
        new = type(self)(**new_cfg)
        new.constraints = (copy.deepcopy(self.constraints) if deep else self.constraints)
        return new

    # @abc.abstractmethod
    def _dump(self, load: Load) -> Dump:
        raise NotImplementedError

    # @abc.abstractmethod
    def _load(self, dump: Dump) -> Load:
        raise NotImplementedError

    def validate_dump(self, dump: Dump):
        for constraint in self.constraints:
            dump = constraint.validate(dump, dump=True)

    def validate_load(self, load: Load):
        for constraint in self.constraints:
            constraint.validate(load, load=True)

    def dump(self, loaded: Load) -> Dump:
        """Cast an origin value to the cast type."""
        self.validate_load(loaded)
        dump = self._dump(loaded)
        self.validate_dump(dump)
        return dump

    def load(self, dump: Dump) -> Load:
        """Cast an origin value to the cast type."""
        self.validate_dump(dump)
        loaded = self._load(dump)
        self.validate_load(loaded)
        return loaded

    def __call__(self, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        return self.copy(**cfg)
