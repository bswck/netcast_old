from __future__ import annotations  # Python 3.8

import abc
import functools
import typing
from typing import Any, TypeVar, Dict, Optional, Literal

from netcast.constants import MISSING
from netcast.exceptions import NetcastError
from netcast.tools.inspection import match_params

if typing.TYPE_CHECKING:
    from typing import Union, Type

    from netcast.driver import DriverMeta
    from netcast.model import Model

    DepT = Union[Type[Model], "Serializer"]
else:
    DepT = TypeVar("DepT")


SettingsT = Optional[Dict[str, Any]]
Phase = Literal["dump", "load", "both"]


class Serializer:
    """A base class for all serializers. A good serializer can dump and load stuff."""

    load_type: type | None = None
    dump_type: type | None = None

    def __init__(
        self,
        *,
        name: str | None = None,
        default: Any = MISSING,
        priority: int = 0,
        coercion_phases: Phase = "both",
        **settings: Any,
    ):
        self.name = name
        self.default = default
        self.contained = False
        self.coercion_phases = coercion_phases
        self.settings = {"priority": priority}
        self.configure(**settings)

    def dump(self, obj, settings: SettingsT = None, /, **kwargs):
        """
        Dump a loaded object.

        NOTE: can be async, depending on the config.
        In that case, the caller must take responsibility for coroutine execution exceptions.
        """
        if settings is None:
            settings = {}
        settings = self.configure(**settings)
        obj = self._cast(obj, "dump", settings)
        try:
            obj = self._dump(obj, settings, **kwargs)
        except Exception as exc:
            raise NetcastError(f"dumping failed: {exc}") from exc
        return obj

    def load(self, obj, settings, /, **kwargs):
        """
        Load a dumped object.

        NOTE: can be async, depending on the config.
        In that case, the caller must take responsibility for coroutine execution exceptions.
        """
        if settings is None:
            settings = {}
        settings = self.configure(**settings)
        try:
            obj = self._load(obj, settings, **kwargs)
        except Exception as exc:
            raise NetcastError(f"loading failed: {exc}") from exc
        obj = self._cast(obj, "load", settings)
        return obj

    def configure(self, **settings):
        """Configure this serializer, possibly applying new settings to public attributes."""
        self.settings.update(settings)
        matched = match_params(self._configure, self.settings)
        self._configure(**matched)
        new_settings = self.settings
        for attr, value in new_settings.items():
            if attr.startswith("_"):
                continue
            if hasattr(self, attr):
                setattr(self, attr, value)
        return new_settings

    def impl(self, driver=None, settings=None, final=False):
        return NotImplemented

    def _configure(self, **settings):
        return

    def _dump(self, obj, settings, **kwargs):
        """Dump an object."""

    def _load(self, obj, settings, **kwargs):
        """Load an object."""

    def load_type_guard(self, obj):
        if self.load_type is None or isinstance(obj, self.load_type):
            return obj
        return self._load_type_guard(obj)

    def _load_type_guard(self, obj):
        return self.load_type(obj)

    def dump_type_guard(self, obj):
        if self.dump_type is None or isinstance(obj, self.dump_type):
            return obj
        return self._dump_type_guard(obj)

    def _dump_type_guard(self, obj):
        return self.dump_type(obj)

    def _sanitize_settings(self, settings: SettingsT) -> SettingsT:
        """Ensure settings are safe to set on this serializer."""
        if settings is None:
            settings = self.settings.copy()
        else:
            settings = {**self.settings, **settings}
        return settings

    def _cast(
        self, obj: Any, phase: Phase, _settings: dict[str, Any]
    ) -> Any:
        """Cast a loaded or dumped object before or after an underlying operation."""
        if phase == "dump":
            if self.coercion_phases in ("dump", "both"):
                obj = self._cast_dump(obj)
        elif phase == "load":
            if self.coercion_phases in ("load", "both"):
                obj = self._cast_load(obj)
        return obj

    def _cast_dump(self, obj: Any) -> Any:
        """Ensure a loaded object has the proper type before dumping it."""
        factory = self.ensure_dump_type
        try:
            obj = factory(obj)
        except Exception as exc:
            raise NetcastError(
                f"could not pre-cast an object {obj!r}\nUsed factory: {factory}"
            ) from exc
        return obj

    def _cast_load(self, obj: Any) -> Any:
        """Ensure a dumped object has the proper type before loading it."""
        factory = self.ensure_load_type
        try:
            obj = factory(obj)
        except Exception as exc:
            raise NetcastError(
                f"could not post-cast an object {obj!r}\nUsed factory: {factory}"
            ) from exc
        return obj

    def __call__(
        self, *, name: str | None = None, default: Any = MISSING, **new_settings: str
    ) -> Serializer:
        """Copy this serializer."""
        if name is None:
            name = self.name
        if default is MISSING:
            default = self.default
        new_settings = {**self.settings, **new_settings}
        return type(self)(name=name, default=default, **new_settings)

    def __repr__(self) -> str:
        repr_default = "" if self.default is MISSING else "default "
        repr_type_name = type(self).__name__
        repr_name = "" if self.name is None else " " + repr(self.name)
        repr_settings = ", ".join(map(
            lambda pair: f"{pair[0]}={pair[1]!r}",
            self.settings.items())
        )
        if self.settings:
            repr_settings = " " + repr_settings.join("()")
        return repr_default + repr_type_name + repr_name + repr_settings

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        try:
            settings = object.__getattribute__(self, "settings")
        except AttributeError:
            settings = {}
        if key in settings:
            settings.update({key: value})

    def __getattr__(self, item):
        value = self.settings.get(item, MISSING)
        if value is MISSING:
            msg = f"{type(self).__name__!r} object has no attribute {item!r}"
            raise AttributeError(msg)
        return value

    def __init_subclass__(cls, **kwargs):
        cls.ensure_load_type = functools.singledispatchmethod(cls.load_type_guard)
        cls.ensure_dump_type = functools.singledispatchmethod(cls.dump_type_guard)


# Don't use yet, it's being tested
class Reference(Serializer):
    """A reference to a certain element of the owner structure."""
    SUPER = "super"

    def __init__(self, identifier: str, **settings: Any):
        self.identifier = identifier
        super().__init__(**settings)

    def resolve(self, context: dict | None = None):
        obj = None
        if context:
            obj = context.get(self.identifier)
            if obj is None:
                supercontext = context.get(self.SUPER, {})
                while supercontext:
                    obj = supercontext.get(self.identifier)
                    supercontext = {}
                    if obj is None:
                        supercontext = context.get(self.SUPER)
        return obj


class Interface(Serializer):
    _impl: Any = NotImplemented
    implements: type | None = None

    def impl(self, driver=None, settings=None, final=False):
        return self._impl

    @property
    @abc.abstractmethod
    def driver(self) -> DriverMeta:
        """Return the driver here."""

    def get_dep(
        self,
        dep: DepT,
        name: str | None = None,
        default: Any = MISSING,
        **dep_settings,
    ) -> DepT:
        if isinstance(dep, type):
            return dep(
                name=name,
                default=default,
                **match_params(dep, dep_settings),
            )
        return dep

    def get_impl(self, dep: DepT, **settings: Any):
        if isinstance(dep, Reference):
            resolved = dep.resolve()
            if resolved is None:
                raise ValueError(f"unresolved reference {dep.identifier!r}")
            dep = resolved

        dep = self.get_dep(dep, **settings)
        settings = {**dep.settings, **settings}
        impl = dep.impl(self.driver, settings, final=True)

        if impl is NotImplemented:
            dep_type = type(dep)
            resolved_type = self.driver.lookup_type(dep_type)

            if resolved_type is not NotImplemented:
                settings.update(
                    name=dep.name,
                    default=dep.default,
                )
                dep = self.get_dep(resolved_type, **settings)
                impl = dep.impl(self.driver, settings, final=True)

        if impl is NotImplemented:
            signature = type(dep).__name__
            if getattr(dep, "name", None) is not None:
                signature += f" ({dep.name})"
            raise NotImplementedError(
                f"{signature} is not supported by the {self.driver.name} driver"
            )

        return impl

    def get_deps(self, deps: tuple[DepT, ...], settings: SettingsT) -> tuple[DepT, ...]:
        final_deps = []
        for dep in deps:
            local_settings = settings.copy()
            local_settings.update(name=dep.name, default=dep.default)
            final_deps.append(self.get_dep(dep, **local_settings))
        return deps

    def get_impls(
        self, deps: tuple[DepT, ...], settings: SettingsT
    ) -> tuple[DepT, ...]:
        impls = tuple(self.get_impl(dep, **settings) for dep in deps)
        return impls

    def __repr__(self):
        return super().__repr__() + " [intermediate interface]"
