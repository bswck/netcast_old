from __future__ import annotations

import abc
import copy
import sys
from typing import Any, ClassVar, Type

from netcast.constants import MISSING
from netcast.exceptions import ArrangementConstructionError
from netcast.plugin import Plugin
from netcast.tools import strings
from netcast.tools.arrangements import ClassArrangement
from netcast.tools.contexts import Context, DoublyLinkedListContextMixin, wrap_method
from netcast.tools.collections import AttributeDict


class DataTypeRegistry(DoublyLinkedListContextMixin, AttributeDict):
    """Data types registry."""

    def __repr__(self):
        super_type = getattr(getattr(self.get('_'), 'cls', None), '__name__', MISSING)
        return '\n'.join((
            f'Supertype: {super_type}',
            f'Data type: {self.cls.__name__}'
        ))


class TypeArrangement(ClassArrangement, config=True):
    __visit_key__: Any = None
    __load_type__: Any = None

    context_class: Type[Context] = DataTypeRegistry

    @classmethod
    def setup_context(cls, context):
        context.cls = cls
        return context

    @classmethod
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
            methods = {  # LBYL
                method: getattr(cls, method) for _, _, method in hooks
            }

        except AttributeError:
            if not feature.is_dependent:
                raise
            return

        else:
            for preceding_hook, trailing_hook, method_name in hooks:
                wrapped = wrap_method(
                    methods[method_name],
                    preceding_hook=preceding_hook,
                    trailing_hook=trailing_hook,
                    initial_shaping=feature.initial_shaping,
                    inform_with_method=feature.inform_with_method,
                    communicate=feature.communicate,
                )
                setattr(cls, method_name, wrapped)

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
            return True

        return taken is MISSING

    @classmethod
    def _get_feature_export(cls, *, attr, feature):
        export = feature.func or feature.default
        ok = cls._check_feature_export(attr=attr, feature=feature, export=export)
        return export if ok else None

    @classmethod
    def _setup_feature(cls, attr, feature):
        if feature.is_hook:
            cls._setup_hook_feature(feature)

        if attr in vars(Serializer) or not attr.isidentifier():
            raise ArrangementConstructionError(
                "exported feature attribute name is illegal"
            )

        export = cls._get_feature_export(attr=attr, feature=feature)
        if export is not None:
            setattr(cls, attr, export)

    def __init_subclass__(cls, **kwargs: Any):
        plugins = ()

        if cls.__base__ is not Serializer and cls.new_context is None:
            cls.new_context = True
            cls.plugins = plugins = tuple(Plugin.get_plugins(cls))

        for plugin in plugins:
            for attr, feature in plugin.exports.items():
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

    def dump(self, loaded, *, context: Context | None = None, **kwargs):
        """Cast an origin value to the cast type."""
        try:
            dump = getattr(self, "_dump")
        except AttributeError as e:
            raise NotImplementedError from e
        else:
            return dump(loaded, context=context, **kwargs)

    def load(self, dumped, *, context: Context | None = None, **kwargs):
        """Cast an origin value to the cast type."""
        try:
            load = getattr(self, "_load")
        except AttributeError:
            raise NotImplementedError
        else:
            return load(dumped, context=context, **kwargs)

    def __call__(self, **cfg: Any) -> Serializer:  # [Origin, Cast]:
        return self.copy(**cfg)

    def __getattr__(self, item):
        return getattr(self.cfg, item)
