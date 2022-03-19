from __future__ import annotations  # Python 3.8

import functools
import inspect
import sys
from typing import ClassVar, Type, TypeVar, TYPE_CHECKING, Any

from netcast import serializers
from netcast.exceptions import NetcastError
from netcast.serializer import Serializer, SettingsT
from netcast.tools.collections import IDLookupDictionary

if TYPE_CHECKING:
    from netcast.serializers import ModelSerializer
    from netcast.model import Model  # noqa: F401


__all__ = ("Driver", "DriverMeta", "driver_serializer", "driver_interface")

ORIGIN_FIELD = "orig_cls"


_M = TypeVar("_M", bound="Model")


class DriverMeta(type):
    _memo: IDLookupDictionary[Model, Serializer]
    _lookup_dict: dict[type, type]

    def _get_model_serializer(
        cls,
        serializer: Type[ModelSerializer],
        /,
        *,
        components: tuple[Any, ...] = (),
        settings: SettingsT = None,
    ) -> ModelSerializer:
        if settings is None:
            settings = {}
        return serializer(*components, **settings)

    # Manual decoration due to some type-checking problems.
    # To be checked in detail.
    get_model_serializer = functools.singledispatchmethod(_get_model_serializer)

    def lookup_model_serializer(cls, model: Model, **settings) -> Serializer:
        components = model.get_suitable_components(**settings).values()
        serializer = cls.get_model_serializer(
            cls.default_model_serializer,
            components=components,
            settings=settings
        )
        return serializer

    def lookup_type(cls, serializer_type: type[Serializer]):
        try:
            return cls._lookup_dict[serializer_type]
        except KeyError:
            return NotImplemented

    def __getattr__(cls, item):
        alias = getattr(serializers, item, None)
        if alias is None or not issubclass(alias, Serializer):
            raise AttributeError(item)
        return object.__getattribute__(cls, alias.__name__)

    def __call__(
        self, model: _M = None, return_serializer=True, **settings
    ) -> ModelSerializer:
        if return_serializer:
            if model is None:
                raise ValueError("`Model` type or instance expected")
            if isinstance(model, type):
                model = model()
            return model._lookup_serializer(self, settings)
        return super().__call__()


class Driver(metaclass=DriverMeta):
    __drivers_registry__: dict[str, Type[Driver]] = {}
    _lookup_dict: ClassVar[dict[Type[Serializer], Type[Serializer]]]

    default_model_serializer = None
    DEBUG: ClassVar[bool]

    def __init_subclass__(cls, driver_name: str | None = None, config: bool = False):
        if config:
            return

        if driver_name is None:
            driver_name = cls._conjure_driver_name(stack_level=2)

        if driver_name in Driver.__drivers_registry__:
            raise ValueError(f"{driver_name!r} driver has already been implemented")

        cls.name = driver_name
        cls.__drivers_registry__[driver_name] = cls
        cls._lookup_dict = {}
        cls._memo = IDLookupDictionary()

        for _, member in inspect.getmembers(cls, _check_impl):
            cls.register(member)

        cls.DEBUG = __debug__

    @staticmethod
    def _conjure_driver_name(stack_level: int = 1) -> str:
        f_globals = inspect.stack()[stack_level][0].f_globals
        driver_name = f_globals.get("DRIVER_NAME", f_globals.get("__name__"))
        if driver_name is None:
            raise ValueError("driver name is required")
        return sys.intern(driver_name)

    @classmethod
    def register(cls, member: type):
        link_to = getattr(member, "orig_cls", member.__base__)
        cls._lookup_dict[link_to] = member
        member_name = member.__name__
        if member_name not in cls.__dict__:
            setattr(cls, member_name, member)
        return member


def _check_impl(member: Any) -> bool:
    return isinstance(member, type) and issubclass(member, Serializer)


def driver_serializer(
    interface_class: type,
    serializer_class: type | None = None,
    origin: type | None = None,
):
    if serializer_class is None:
        raise NetcastError("no serializer has been set on this adapter")
    impl = type(
        serializer_class.__name__,
        (serializer_class, interface_class),
        {ORIGIN_FIELD: (serializer_class if origin is None else origin)},
    )
    return impl


def driver_interface(interface_class: type, origin: type | None = None):
    if origin is None:
        origin = getattr(interface_class, ORIGIN_FIELD, None)
    return functools.partial(driver_serializer, interface_class, origin=origin)
