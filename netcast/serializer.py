from __future__ import annotations  # Python 3.8

import abc
import enum
from typing import Any, Generator, TypeVar, TYPE_CHECKING, Dict, Optional, Literal

from netcast.constants import MISSING
from netcast.exceptions import NetcastError
from netcast.tools.inspection import match_params

if TYPE_CHECKING:
    from netcast.driver import DriverMeta


SettingsT = Optional[Dict[str, Any]]
DepT = TypeVar("DepT")


class Phase(enum.IntFlag):
    PRE = 1
    POST = 2


class Serializer:
    """A base class for all serializers. A good serializer can dump and load stuff."""

    load_type: type | None = None
    dump_type: type | None = None

    def __init__(
        self,
        *,
        name: str | None = None,
        default: Any = MISSING,
        coercion_phases: int = Phase.PRE | Phase.POST,
        **settings: Any,
    ):
        super().__init__()
        self.name = name
        self.default = default
        self.contained = False
        self.coercion_phases = coercion_phases
        self.settings = {}
        self.configure(**settings)

    def dump(self, obj, *, settings: SettingsT = None, **kwargs: Any):
        """
        Dump a loaded object.

        NOTE: can be async, depending on the config.
        In that case the caller must take responsibility for coroutine execution exceptions.
        """
        self.configure(**{**self.settings, **kwargs})
        obj = self._cast_object(obj, Phase.PRE, settings)
        try:
            obj = self._dump(obj, settings=settings, **kwargs)
        except Exception as exc:
            raise NetcastError(f"dumping failed: {exc}") from exc
        return obj

    def load(self, obj, *, settings: SettingsT = None, **kwargs):
        """
        Load a dumped object.

        NOTE: can be async, depending on the config.
        In that case the caller must take responsibility for coroutine execution exceptions.
        """
        self.configure(**{**self.settings, **kwargs})
        try:
            obj = self._load(obj, settings=settings, **kwargs)
        except Exception as exc:
            raise NetcastError(f"loading failed: {exc}") from exc
        obj = self._cast_object(obj, Phase.POST, settings)
        return obj

    def configure(self, **settings):
        """Configure this serializer, possibly applying new settings to public attributes."""
        self.settings.update(**settings)
        matched = match_params(self.configure, settings)
        self._configure(**matched)
        new_settings = self.settings
        for attr, value in new_settings.items():
            if attr.startswith("_"):
                continue
            if hasattr(self, attr):
                setattr(self, attr, value)

    def _configure(self, **settings):
        return

    def _dump(self, obj, settings, **kwargs):
        """Dump an object."""

    def _load(self, obj, settings, **kwargs):
        """Load an object."""

    def _sanitize_settings(self, settings: SettingsT) -> SettingsT:
        """Ensure settings are safe to set on this serializer."""
        if settings is None:
            settings = self.settings.copy()
        else:
            settings = {**self.settings, **settings}
        return settings

    def _cast_object(
        self, obj: Any, phase: Literal[Phase.PRE, Phase.POST], _settings: dict[str, Any]
    ) -> Any:
        """Cast a loaded or dumped object before or after an underlying operation."""
        if phase == Phase.PRE:
            if self.coercion_phases & Phase.PRE:
                obj = self._pre_cast(obj)
        elif phase == Phase.POST:
            if self.coercion_phases & Phase.POST:
                obj = self._post_cast(obj)
        return obj

    def _pre_cast(self, dump: Any) -> Any:
        """Ensure a dumped object has the proper type before loading it."""
        factory = getattr(self, "load_type_factory", self.load_type)
        if factory is None or (isinstance(factory, type) and isinstance(dump, factory)):
            return dump
        try:
            obj = factory(dump)
        except Exception as exc:
            raise NetcastError(
                f"could not pre-cast an object {dump!r}\nUsed factory: {factory}"
            ) from exc
        return obj

    def _post_cast(self, load: Any) -> Any:
        """Ensure a loaded object has the proper type before dumping it."""
        factory = getattr(self, "dump_type_factory", self.dump_type)
        if factory is None or (isinstance(factory, type) and isinstance(load, factory)):
            return load
        try:
            obj = factory(load)
        except Exception as exc:
            raise NetcastError(
                f"could not post-cast an object {load!r}\nUsed factory: {factory}"
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
        default = "" if self.default is MISSING else "default "
        type_name = type(self).__name__
        name = "" if self.name is None else " " + repr(self.name)
        settings = f" ({self.settings})" if self.settings else ""
        return default + type_name + name + settings

    @property
    def impl(self):
        return NotImplemented


class Interface(Serializer):
    _impl: Any = None
    orig_cls: type | None = None

    @property
    def impl(self):
        return self._impl

    @property
    @abc.abstractmethod
    def driver(self) -> DriverMeta:
        """Return the driver here."""

    def get_dep(
        self,
        dep: DepT,
        *,
        name: str | None = None,
        default: Any = MISSING,
        **dep_settings,
    ) -> DepT:
        dep_settings = {**self.settings, **dep_settings}
        if isinstance(dep, type):
            return dep(
                name=name,
                default=default,
                **match_params(dep, dep_settings),
            )
        return dep

    def get_impl(self, dep: DepT, **settings):
        dep = self.get_dep(dep, **settings)
        settings = {**settings, **self.settings, **dep.settings}
        impl = dep.impl

        if impl is NotImplemented:
            dep_type = type(dep)
            dep = self.get_dep(
                self.driver.lookup_type(dep_type),
                name=dep.name,
                default=dep.default,
                **settings,
            )
            impl = dep.impl

        if impl is NotImplemented:
            signature = type(dep).__name__
            if getattr(dep, "name", None) is not None:
                signature += f" ({dep.name})"
            raise NotImplementedError(
                f"{signature} is not supported by the {self.driver.name} driver"
            )

        return impl

    def get_deps(self, deps: tuple[DepT, ...], settings: SettingsT) -> Generator[DepT]:
        return (
            self.get_dep(dep, name=dep.name, default=dep.default, **settings)
            for dep in deps
        )

    def get_impls(self, deps: tuple[DepT, ...], settings: SettingsT) -> Generator:
        return (self.get_impl(dep, **settings) for dep in deps)

    def __repr__(self):
        return super().__repr__() + " interface"
