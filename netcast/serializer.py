from __future__ import annotations

import abc
import copy
import enum
import sys
from typing import Any, ClassVar, final, Type, Literal

from netcast import ClassArrangement, Context, DoublyLinkedListContextMixin
from netcast.plugin import Plugin
from netcast.tools import strings
from netcast.tools.contexts import wrap_method
from netcast.tools.symbol import Symbol
from netcast.tools.collections import AttributeDict


class ConstraintPolicy(enum.Enum):
    ignore = 'ignore'
    reshape = 'reshape'
    strict = 'strict'


_Policies = Literal['ignore', 'reshape', 'strict']


class ConstraintError(ValueError):
    """A constraint failed."""


class Constraint(metaclass=abc.ABCMeta):
    def __init__(self, policy: _Policies | ConstraintPolicy = 'strict', **cfg: Any):
        if isinstance(policy, str):
            valid_opts = ConstraintPolicy._value2member_map_
            if policy not in valid_opts:
                raise ValueError(f'invalid constraint policy: {policy!r}')
            policy = valid_opts[policy]
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.policy = policy
        self.setup()

    def setup(self):
        """Constraint setup."""

    @staticmethod
    def _validate_default(obj):
        return obj or True

    validate_dump = _validate_default
    validate_load = _validate_default

    @staticmethod
    def _reshape_default(obj):
        return obj

    reshape_load = _reshape_default
    reshape_dump = _reshape_default

    def validate(self, obj, **dump_xor_load):
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

    @classmethod
    def preprocess_context(cls, context):
        context.impl = cls
        return context

    @classmethod
    @final
    def subcontext_key(cls, *__related_contexts):
        """Return the key for all the subcontexts."""
        if cls.__visit_key__ == getattr(cls.__base__, '__visit_key__', None):
            cls.__visit_key__ = sys.intern(cls.__name__)
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
            cls.plugins = plugins = Plugin.get_plugins(cls)

        for plugin in plugins:
            for attr, feature in plugin.__features__.items():
                if feature.is_hook:
                    hooks = []

                    if feature.before == feature.after:
                        hooks.append((feature.func, feature.func, feature.before))

                    else:
                        if feature.before:
                            hooks.append((feature.func, None, feature.before))

                        if feature.after:
                            hooks.append((None, feature.func, feature.after))

                    try:
                        hooked_methods = {  # LBYL
                            method: getattr(cls, method) for _, _, method in hooks
                        }

                    except AttributeError:
                        if not feature.dependent:
                            raise
                        continue

                    else:
                        for precede_hook, finalize_hook, method in hooks:
                            setattr(
                                cls,
                                method,
                                wrap_method(
                                    hooked_methods[method],
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
                read = getattr(cls, attr, missing)

                if export is feature.func:
                    if read not in (feature, export, missing):
                        raise ValueError(
                            f'feature {strings.truncate(attr)}() '
                            'has already been added. Set override=True on it to '
                            'override all the features'
                        )

                else:
                    if read is not missing:
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

    def dump(
            self,
            loaded,
            context: Context | None = None,
            **kwargs
    ):
        """Cast an origin value to the cast type."""
        try:
            dump = getattr(self, '_dump')
        except AttributeError:
            raise NotImplementedError
        else:
            return dump(loaded, context=context, **kwargs)

    def load(
            self,
            dumped,
            context: Context | None = None,
            **kwargs
    ):
        """Cast an origin value to the cast type."""
        try:
            load = getattr(self, '_load')
        except AttributeError:
            raise NotImplementedError
        else:
            return load(dumped, context=context, **kwargs)

    def __call__(self, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        return self.copy(**cfg)
