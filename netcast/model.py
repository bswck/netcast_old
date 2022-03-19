from __future__ import annotations  # Python 3.8

import collections.abc
import functools
import inspect
from typing import Any, ClassVar, Type, TypeVar, Union

from netcast.constants import MISSING, GREATEST
from netcast.driver import Driver, DriverMeta
from netcast.serializer import Serializer, SettingsT
from netcast.stack import Stack, VersionAwareStack


__all__ = (
    "check_component",
    "ComponentDescriptor",
    "ComponentArgumentT",
    "ComponentT",
    "model",
    "Model",
    "ProxyDescriptor",
)


class _BaseDescriptor:
    component: ComponentT

    def __getattr__(self, attribute_name: str) -> Any:
        return getattr(self.component, attribute_name)


class ComponentDescriptor(_BaseDescriptor):
    _state = MISSING

    def __init__(self, component: ComponentT):
        self.component = component

    @property
    def state(self) -> Any:
        return self._state

    def __get__(self, instance: Model | None, owner: Type[Model] | None) -> Any:
        if instance is None:
            return self
        return self.state

    def __set__(self, instance: Model | None = None, state: Any = MISSING):
        self._state = state

    def __call__(self, state) -> Any:
        self.__set__(state=state)
        return state


class ProxyDescriptor(_BaseDescriptor):
    def __init__(self, ancestor: ComponentDescriptor):
        self.ancestor = ancestor

    @property
    def component(self) -> ComponentT:
        return self.ancestor.component

    def __get__(self, instance: Model | None, owner: Type[Model] | None) -> Any:
        if instance is None:
            return self
        return self.state

    def __set__(self, instance: Model | None = None, new_state: Any = MISSING):
        self.component.__set__(instance, new_state)

    def __call__(self, state: Any) -> Any:
        self.component.__set__(state=state)
        return state


@functools.total_ordering
class Model:
    stack: ClassVar[Stack]
    settings: ClassVar[dict[str, Any]]
    descriptor_class = ComponentDescriptor
    descriptor_alias_class = ProxyDescriptor
    name: str

    def __init__(
        self,
        name: str | None = None,
        defaults: dict[str, Any] | None = None,
        **settings,
    ):
        super().__init__()

        if name is None:
            name = type(self).__name__
        self.name = name

        if defaults is None:
            defaults = {}
        self._defaults = defaults

        for key in set(settings):
            if key in self._descriptors:
                self[key] = settings.pop(key)

        self.contained: bool = False
        self.settings = {**self.settings, **settings}

    @property
    def default(self) -> Any:
        defaults = self._defaults.copy()
        for name, desc in self._descriptors.items():
            default = desc.component.default
            if default is not MISSING:
                defaults[name] = default
        return defaults

    def _lookup_serializer(self, driver_or_serializer, settings: SettingsT = None):
        if settings is None:
            settings = {}
        settings = {**settings, **self.settings}
        if isinstance(driver_or_serializer, DriverMeta):
            driver = driver_or_serializer
            serializer = driver.lookup_model_serializer(self, **settings)
        else:
            serializer = driver_or_serializer
            serializer = serializer.get_dep(
                serializer, name=self.name, default=self.default, **self.settings
            )
        return serializer

    @property
    def state(self) -> dict:
        return self.get_state()

    def get_state(self, empty=MISSING, **settings: Any) -> dict:
        descriptors = self._get_suitable_descriptors(**settings)
        state = {}

        for name, descriptor in descriptors.items():
            value = descriptor.state

            if value is MISSING:
                value = descriptor.component.default

            if value is MISSING:
                if empty is not MISSING:
                    value = empty
                else:
                    raise ValueError(
                        f"missing required {type(descriptor.component).__name__} "
                        f"value for serializer named {descriptor.component.name!r}"
                    )
            state[name] = value
        return state

    def get_suitable_components(self, **settings: Any) -> dict[Any, ComponentT]:
        settings = {**settings, **self.settings}
        return self.stack.get_suitable_components(settings)

    def _get_suitable_descriptors(
        self, settings: SettingsT
    ) -> dict[Any, ComponentDescriptor]:
        namespace = set(self.get_suitable_components(**settings))
        descriptors = {
            name: desc for name, desc in self._descriptors.items() if name in namespace
        }
        return descriptors

    def bind(self, **values):
        for key, value in values.items():
            self[key] = value
        return self

    def dump(
        self, driver_or_serializer: Type[Driver] | Serializer, **settings: Any
    ) -> Any:
        serializer = self._lookup_serializer(driver_or_serializer, settings)
        return serializer.dump(self.get_state(), settings=settings)

    def load(
        self, driver_or_serializer: Type[Driver] | Serializer, dump: Any, **settings
    ) -> Model:
        serializer = self._lookup_serializer(driver_or_serializer, settings)
        return self.load_state(serializer.load(dump, settings=settings))

    def load_state(self, load: Any):
        state = self.parse_state(load)
        self.set_state(state)
        return self

    @functools.singledispatchmethod
    def parse_state(self, load: Any) -> dict | tuple[tuple[str, Any], ...]:
        raise TypeError(f"unsupported state type: {type(load).__name__}")

    @parse_state.register
    def parse_sequence_state(self, load: collections.abc.Sequence) -> "dict[str, Any]":
        return dict(zip(self._descriptors, load))

    @parse_state.register
    def parse_mapping_state(self, load: collections.abc.Mapping) -> dict:
        return dict(load)

    def set_state(self, state: dict):
        if callable(getattr(state, "items", None)):
            state = state.items()

        for item, value in state:
            try:
                self[item] = value
            except KeyError:
                pass

    def __iter__(self):
        for name in self._descriptors:
            yield name, self[name]

    def __setitem__(self, key: Any, value: Any):
        self._descriptors[key].__set__(self, value)

    def __getitem__(self, key: Any):
        return self._descriptors[key].__get__(self, None)

    def __setattr__(self, key: str, value: Any):
        if key in self._descriptors:
            self._descriptors[key].__set__(self, value)
            return

        object.__setattr__(self, key, value)

    def __eq__(self, other: Model):
        if not isinstance(other, Model):
            return NotImplemented

        return self.get_state() == other.get_state()

    def __lt__(self, other: Model):
        if not isinstance(other, Model):
            return NotImplemented

        state = self.get_state()
        other_state = dict.fromkeys(self.get_state(), GREATEST)
        input_state = other.get_state()

        for key in state.keys() & input_state.keys():
            other_state[key] = input_state[key]

        return tuple(state.values()) < tuple(other_state.values())

    @classmethod
    def _build_from_members(cls):
        cls._descriptors = descriptors = {}
        seen = {}

        for attribute_name, component in inspect.getmembers(cls, check_component):
            name = attribute_name
            seen_descriptor = seen.get(id(component))

            if seen_descriptor is None:
                transformed = cls.stack.add(
                    component, default_name=attribute_name, settings=cls.settings
                )
                descriptor = cls.descriptor_class(transformed)
                setattr(cls, transformed.name, descriptor)
            else:
                descriptor = seen_descriptor
                alias_descriptor = cls.descriptor_alias_class(descriptor)
                setattr(cls, attribute_name, alias_descriptor)
            descriptors[name] = descriptor
            seen[id(component)] = descriptor
        seen.clear()

    @classmethod
    def _build_from_stack(cls, **settings):
        suitable_components = cls.stack.get_suitable_components(**settings)
        cls._descriptors = descriptors = {}

        for idx, (name, component) in enumerate(suitable_components.items()):
            descriptor = descriptors[name] = cls.descriptor_class(component)
            setattr(cls, name, descriptor)

    def __init_subclass__(
        cls,
        stack: Stack = None,
        from_members: bool | None = None,
        stack_class: Type[Stack] = VersionAwareStack,
        **settings: Any,
    ):
        if from_members is None:
            from_members = stack is None

        if stack is None:
            stack = stack_class()

        cls.stack = stack
        cls.settings = settings
        cls.name = cls.__name__.casefold()

        if from_members:
            cls._build_from_members()
        else:
            cls._build_from_stack(**settings)


ComponentT = TypeVar("ComponentT", Serializer, Model)
ComponentArgumentT = Union[ComponentT, Type[ComponentT]]


def check_component(obj: Any, acknowledge_type: bool = True) -> bool:
    is_instance = isinstance(obj, (Serializer, Model))
    is_type = (
        acknowledge_type
        and isinstance(obj, type)
        and issubclass(obj, (Serializer, Model))
    )
    return is_instance or is_type


def model(
    *components: ComponentArgumentT,
    stack: Stack | None = None,
    name: str | None = None,
    model_class: Type[Model] = Model,
    model_metaclass: Type[Type] = type,
    stack_class: Type[Stack] = VersionAwareStack,
    **settings,
):
    if stack is None:
        stack = stack_class()
    for component in components:
        stack.add(component, settings=settings)
    if name is None:
        name = "model_" + str(id(stack))
    return model_metaclass(name, (model_class,), {}, stack=stack, **settings)
