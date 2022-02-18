from __future__ import annotations  # Python 3.8

import abc
import enum
import functools
from typing import Any, ClassVar, Generator, TypeVar, TYPE_CHECKING

from netcast.constants import MISSING
from netcast.exceptions import NetcastError
from netcast.tools.inspection import force_compliant_kwargs

if TYPE_CHECKING:
    from netcast.driver import DriverMeta


_DependencyT = TypeVar("_DependencyT")


class Serializer:
    """
    A base class for all serializers. A good serializer can dump and load stuff.
    """

    load_type: ClassVar[Symbol | type] = MISSING
    dump_type: ClassVar[Symbol | type] = MISSING

    name: str | None
    settings: dict[str, Any]
    default: Any

    __taken__: bool

    def __init__(self, *, name=None, default=MISSING, **settings):
        self.name = name
        self.default = default
        self.settings = settings

    def dump(self, load, *, settings: Any = None, **kwargs):
        """
        Dump a loaded object.

        NOTE: can be async, depending on the config.
        In that case the caller must take responsibility for coroutine execution exceptions.
        """
        try:
            dump = getattr(self, "_dump")
        except AttributeError as e:
            raise NotImplementedError from e
        else:
            try:
                return dump(load, settings=settings, **kwargs)
            except Exception as exc:
                raise NetcastError(f"dumping failed: {exc}") from exc

    def load(self, dump, *, settings: Any = None, **kwargs):
        """
        Load from a dumped object.

        NOTE: can be async, depending on the config.
        In that case the caller must take responsibility for coroutine execution exceptions.
        """
        try:
            load = getattr(self, "_load")
        except AttributeError:
            raise NotImplementedError
        else:
            try:
                return load(dump, settings=settings, **kwargs)
            except Exception as exc:
                raise NetcastError(f"loading failed: {exc}") from exc

    def _coerce_load_type(self, load):
        factory = getattr(self, "load_type_factory", self.load_type)
        if factory is MISSING:
            raise TypeError("incomplete data type")
        return factory(load)

    def _coerce_dump_type(self, dump):
        factory = getattr(self, "dump_type_factory", self.dump_type)
        if factory is MISSING:
            raise TypeError("incomplete data type")
        return factory(dump)

    def __call__(self, *, name=None, default=MISSING, **overridden_settings) -> Serializer:
        if name is None:
            name = self.name
        if default is MISSING:
            default = self.default
        settings = {**self.settings, **overridden_settings}
        return type(self)(
            name=name,
            default=default,
            **settings
        )

    @property
    def impl(self):
        return NotImplemented

    @functools.singledispatchmethod
    def load_type_factory(self, obj):
        raise NotImplementedError


class Coercion(enum.IntFlag):
    LOAD_TYPE_BEFORE_DUMPING = 1 << 0
    LOAD_TYPE_AFTER_LOADING = 1 << 1
    DUMP_TYPE_BEFORE_LOADING = 1 << 2
    DUMP_TYPE_AFTER_DUMPING = 1 << 3


class Interface(Serializer):  # abc.ABC
    _impl: Any = None
    __netcast_origin__ = None

    def __init__(self, *, name, coercion_flags=0, **settings):
        super().__init__(name=name, **settings)
        self.settings["coercion_flags"] = self.coercion_flags = coercion_flags

    @property
    def impl(self):
        return self._impl

    @property
    @abc.abstractmethod
    def driver(self) -> DriverMeta:
        """Return the driver here."""

    def get_dependency(
            self,
            dependency: _DependencyT,
            *,
            name: str | None = None,
            default: Any = MISSING,
            **dependency_settings
    ) -> _DependencyT:
        dependency_settings = {**self.settings, **dependency_settings}
        if isinstance(dependency, type):
            return dependency(
                name=name,
                default=default,
                **force_compliant_kwargs(dependency, dependency_settings)
            )
        return dependency

    def get_impl(
            self,
            dependency: _DependencyT,
            **settings
    ):
        dependency = self.get_dependency(dependency, **settings)
        settings = {**settings, **self.settings, **dependency.settings}
        impl = dependency.impl

        if impl is NotImplemented:
            impl = self.get_dependency(
                self.driver.lookup(type(dependency)),
                name=dependency.name,
                default=dependency.default,
                **settings
            ).impl

        if impl is NotImplemented:
            signature = type(dependency).__name__
            if getattr(dependency, "name", None) is not None:
                signature += f" ({dependency.name})"
            raise NotImplementedError(
                f"{signature} is not supported by the {self.driver.name} driver"
            )

        return impl

    def get_dependencies(
            self,
            dependencies: tuple[_DependencyT, ...],
            settings: dict
    ) -> Generator[_DependencyT]:
        return (
            self.get_dependency(
                dependency,
                name=dependency.name,
                default=dependency.default,
                **settings
            )
            for dependency in dependencies
        )

    def get_impls(self, dependencies, settings):
        return (self.get_impl(dependency, **settings) for dependency in dependencies)

    def _load(self, dump, *, settings=None):
        if settings is None:
            settings = {}
        if self.coercion_flags & Coercion.DUMP_TYPE_BEFORE_LOADING:
            dump = self._coerce_load_type(dump)
        load = self.impl.parse(dump, **settings)
        if self.coercion_flags & Coercion.LOAD_TYPE_AFTER_LOADING:
            load = self._coerce_load_type(load)
        return load

    def _dump(self, load, *, settings=None):
        if settings is None:
            settings = {}
        if self.coercion_flags & Coercion.LOAD_TYPE_BEFORE_DUMPING:
            load = self._coerce_load_type(load)
        dump = self.impl.build(load, **settings)
        if self.coercion_flags & Coercion.DUMP_TYPE_AFTER_DUMPING:
            dump = self._coerce_dump_type(dump)
        return dump
