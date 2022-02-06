from __future__ import annotations

import abc
import copy
import sys
from typing import Any, ClassVar, final, Type

from netcast.constants import MISSING
from netcast.exceptions import ArrangementConstructionError
from netcast.plugin import Plugin
from netcast.tools import strings
from netcast.tools.arrangements import ClassArrangement
from netcast.tools.contexts import Context, DoublyLinkedListContextMixin, wrap_method
from netcast.tools.collections import AttributeDict


class DataTypeRegistry(DoublyLinkedListContextMixin, AttributeDict):
    """Data types registry."""


class TypeArrangement(ClassArrangement, config=True):
    __visit_key__: Any = None
    __load_type__: Any = None

    context_class: Type[Context] = DataTypeRegistry

    @classmethod
    def setup_context(cls, context):
        context.cls = cls
        return context

    @classmethod
    @final
    def subcontext_key(cls, *__related_contexts):
        """Return the key for all the subcontexts."""
        if cls.__visit_key__ == getattr(cls.__base__, "__visit_key__", None):
            cls.__visit_key__ = sys.intern(cls.__name__)
        return cls.__visit_key__


class Serializer(TypeArrangement, metaclass=abc.ABCMeta):
    """
    A base class for all serializers. A good serializer can dump and load stuff.
    """

    plugins: ClassVar[tuple[Plugin, ...]] = ()

    def __init__(self, **cfg: Any):
        super().__init__()
        self.cfg: AttributeDict[str, Any] = AttributeDict(cfg)
        self.setup()

    def setup(self):
        """Simple setup callback. Does nothing by default."""

    @classmethod
    def _setup_hook_feature(cls, feature):
        hooks = []

        if feature.call_before == feature.call_after:
            hooks.append((feature.func, feature.func, feature.call_before))

        else:
            if feature.call_before:
                hooks.append((feature.func, None, feature.call_before))

            if feature.call_after:
                hooks.append((None, feature.func, feature.call_after))

        try:
            hooked_methods = {  # LBYL
                method: getattr(cls, method) for _, _, method in hooks
            }

        except AttributeError:
            if not feature.is_dependent:
                raise
            return

        else:
            for precede_hook, finalize_hook, method in hooks:
                setattr(
                    cls,
                    method,
                    wrap_method(
                        hooked_methods[method],
                        precede_hook=precede_hook,
                        finalize_hook=finalize_hook,
                        precedential_reshaping=feature.precedential_reshaping,
                        hook_takes_method=feature.hook_takes_method,
                        finalizer_takes_result=feature.finalizer_takes_result,
                    ),
                )

    @classmethod
    def _check_feature_export(cls, *, attr, feature, export):
        taken = getattr(cls, attr, MISSING)

        if export is feature.func:
            if taken not in (feature, export, MISSING):
                raise ArrangementConstructionError(
                    f"feature {strings.truncate(attr)}() "
                    "has already been added. Set override=True on it to "
                    "override all the features"
                )

        else:
            if taken is not MISSING:
                return

    @classmethod
    def _get_feature_export(cls, *, attr, feature):
        export = feature.func or feature.default
        cls._check_feature_export(attr=attr, feature=feature, export=export)
        return export

    @classmethod
    def _setup_feature(cls, attr, feature):
        if feature.is_hook:
            cls._setup_hook_feature(feature)

        if attr in vars(Serializer):
            raise ArrangementConstructionError(
                "exported feature attribute name is illegal"
            )

        export = cls._get_feature_export(attr=attr, feature=feature)
        setattr(cls, attr, export)

    def __init_subclass__(cls, **kwargs: Any):
        plugins = ()

        if cls.__base__ is not Serializer and cls.new_context is None:
            cls.new_context = True
            cls.plugins = plugins = Plugin.get_plugins(cls)

        for plugin in plugins:
            for attr, feature in plugin.__features__.items():
                cls._setup_feature(attr, feature)

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

    def dump(self, loaded, context: Context | None = None, **kwargs):
        """Cast an origin value to the cast type."""
        try:
            dump = getattr(self, "_dump")
        except AttributeError as e:
            raise NotImplementedError from e
        else:
            return dump(loaded, context=context, **kwargs)

    def load(self, dumped, context: Context | None = None, **kwargs):
        """Cast an origin value to the cast type."""
        try:
            load = getattr(self, "_load")
        except AttributeError:
            raise NotImplementedError
        else:
            return load(dumped, context=context, **kwargs)

    def __call__(self, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        return self.copy(**cfg)
