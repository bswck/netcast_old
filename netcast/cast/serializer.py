from __future__ import annotations

import abc
import copy
import enum
from typing import Any, ClassVar, Generic, TypeVar, final, Type, Literal

from netcast import ClassArrangement, Context, DoublyLinkedListContextMixin
from netcast.cast.plugin import Plugin, get_plugins
from netcast.contexts import wrap_method
from netcast.toolkit import strings
from netcast.toolkit.symbol import Symbol
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
    def __init__(self, policy: _Policies | ConstraintPolicy = 'strict', **cfg: Any):
        if isinstance(policy, str):
            valid_opts = ConstraintPolicy._value2member_map_
            if policy not in valid_opts:
                raise ValueError(f'invalid constraint policy: {policy!r}')
            policy = valid_opts[policy]
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
    """
    A base class for all serializers. A good serializer can dump and load stuff.
    """

    plugins: ClassVar[tuple[Plugin, ...]] = ()

    def __init__(self, **cfg: Any):
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.setup()

    def setup(self):
        """Simple setup callback. Does nothing by default."""

    def __init_subclass__(
            cls,
            **kwargs: Any
    ):
        plugins = ()

        if cls.__base__ is not Serializer and cls.new_context is None:
            cls.new_context = True
            cls.plugins = plugins = get_plugins(cls)

        for plugin in plugins:
            for attr, feature in plugin.__features__.items():
                if feature.is_hook:
                    hooked_method = precede_hook = finalize_hook = None

                    if feature.before == feature.after:
                        hooked_method = feature.before
                        precede_hook = feature.func
                        finalize_hook = feature.func

                    else:
                        if feature.before:
                            hooked_method = feature.before
                            precede_hook = feature.func
                        if feature.after:
                            hooked_method = feature.after
                            precede_hook = feature.func

                    try:
                        method = getattr(cls, hooked_method)  # LBYL
                    except AttributeError:
                        if not feature.dependent:
                            raise
                        continue
                    else:
                        setattr(
                            cls,
                            hooked_method,
                            wrap_method(
                                method,
                                precede_hook=precede_hook,
                                finalize_hook=finalize_hook,
                                pass_method=feature.pass_method,
                                finalizer_takes_result=feature.finalizer_takes_result
                            )
                        )

                export = feature.func or feature.default

                if attr in vars(Serializer):
                    raise ValueError('exported feature attribute name is illegal')

                missing = Symbol()
                read_attr = getattr(cls, attr, missing)

                if export is feature.func:
                    if read_attr not in (feature, export, missing):
                        raise ValueError(
                            f'feature {strings.truncate(attr)}() '
                            'has already been added. Set override=True on it to '
                            'override all the features'
                        )

                else:
                    if read_attr is not missing:
                        continue

                setattr(cls, attr, export)

        super().__init_subclass__(**kwargs)

    def copy(self, deep=False, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        """Copy this type."""
        if deep:
            new_cfg = {**copy.deepcopy(self.cfg), **cfg}
        else:
            new_cfg = self.cfg
            new_cfg.update(cfg)
        new = type(self)(**new_cfg)
        return new

    # @abc.abstractmethod
    def _default_cast(self, load_or_dump: Load | Dump, context=None) -> Load | Dump:
        raise NotImplementedError

    _dump = _default_cast
    _load = _default_cast

    def dump(self, loaded: Load, context: Context | None = None) -> Dump:
        """Cast an origin value to the cast type."""
        dump = self._dump(loaded, context)
        return dump

    def load(self, dump: Dump, context: Context | None = None) -> Load:
        """Cast an origin value to the cast type."""
        loaded = self._load(dump, context)
        return loaded

    def __call__(self, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        return self.copy(**cfg)
