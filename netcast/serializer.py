from __future__ import annotations  # Python 3.8

import abc
import enum
from typing import Any, ClassVar, Generator, TypeVar, TYPE_CHECKING, Dict

from netcast.constants import MISSING
from netcast.exceptions import NetcastError
from netcast.expressions import ExpressionOps
from netcast.tools.inspection import force_compliant_kwargs
from netcast.tools.symbol import Symbol

if TYPE_CHECKING:
    from netcast.driver import DriverMeta


SettingsT = TypeVar("SettingsT", Dict[str, Any], type(None))
DependencyT = TypeVar("DependencyT")


class Serializer(ExpressionOps):
    """A base class for all serializers. A good serializer can dump and load stuff."""

    load_type: ClassVar[Symbol | type] = MISSING
    dump_type: ClassVar[Symbol | type] = MISSING

    def __init__(self, *, name=None, default=MISSING, **settings: Any):
        super().__init__()
        self.name: str | None = name
        self.default: Any = default
        self.settings: dict[str, Any] = settings
        self.contained: bool = False

    def dump(self, load, *, settings: SettingsT = None, **kwargs: Any):
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

    def load(self, dump, *, settings: SettingsT = None, **kwargs):
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

    def _coerce_load_type(self, load: Any) -> load_type:
        factory = getattr(self, "load_type_factory", self.load_type)
        if factory is MISSING:
            raise TypeError("incomplete data type")
        return factory(load)

    def _coerce_dump_type(self, dump: Any) -> dump_type:
        factory = getattr(self, "dump_type_factory", self.dump_type)
        if factory is MISSING:
            raise TypeError("incomplete data type")
        return factory(dump)

    def __call__(
            self, *,
            name: str | None = None,
            default: Any = MISSING,
            **new_settings: str
    ) -> Serializer:
        if name is None:
            name = self.name
        if default is MISSING:
            default = self.default
        new_settings = {**self.settings, **new_settings}
        return type(self)(name=name, default=default, **new_settings)

    def __repr__(self) -> str:
        return (
            f"<{'' if self.default is MISSING else 'default '}{type(self).__name__}"
            f"{'' if self.name is None else ' ' + repr(self.name)} (settings -> {self.settings})"
            ">"
        )

    @property
    def impl(self):
        return NotImplemented


class Coercion(enum.IntFlag):
    LOAD_TYPE_BEFORE_DUMPING = 1 << 0
    LOAD_TYPE_AFTER_LOADING = 1 << 1
    DUMP_TYPE_BEFORE_LOADING = 1 << 2
    DUMP_TYPE_AFTER_DUMPING = 1 << 3


class Interface(Serializer):  # abc.ABC
    _impl: Any = None
    nc_origin = None

    def __init__(
            self, *,
            name: str | None,
            coercion_flags: int = 0,
            **settings
    ):
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
        dependency: DependencyT,
        *,
        name: str | None = None,
        default: Any = MISSING,
        **dependency_settings,
    ) -> DependencyT:
        dependency_settings = {**self.settings, **dependency_settings}
        if isinstance(dependency, type):
            return dependency(
                name=name,
                default=default,
                **force_compliant_kwargs(dependency, dependency_settings),
            )
        return dependency

    def get_impl(self, dependency: DependencyT, **settings):
        dependency = self.get_dependency(dependency, **settings)
        settings = {**settings, **self.settings, **dependency.settings}
        impl = dependency.impl

        if impl is NotImplemented:
            impl = self.get_dependency(
                self.driver.lookup(type(dependency)),
                name=dependency.name,
                default=dependency.default,
                **settings,
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
        self, dependencies: tuple[DependencyT, ...], settings: dict
    ) -> Generator[DependencyT]:
        return (
            self.get_dependency(
                dependency, name=dependency.name, default=dependency.default, **settings
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

    def __repr__(self):
        return super().__repr__()[:-1] + " interface>"
