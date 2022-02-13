from __future__ import annotations

import collections.abc
import functools
import inspect
import threading
import typing

from netcast.constants import LEAST, GREATEST, MISSING
from netcast.driver import Driver
from netcast.serializer import Serializer
from netcast.tools import strings


class ComponentStack:
    def __init__(self):
        self._components = []
        self._lock = threading.RLock()

    @classmethod
    def transform_submodel(cls, submodel) -> Model:
        return submodel

    @classmethod
    def transform_serializer(
            cls,
            component: Serializer,
            settings: dict | None = None
    ) -> Serializer:
        if settings is None:
            settings = {}
        return component(**settings)

    def transform_component(
            self,
            component, *,
            settings=None,
            default_name=None
    ) -> ComponentT | None:
        if settings is None:
            settings = {}
        settings.setdefault("name", default_name)
        if isinstance(component, type) and not issubclass(component, Model):
            component = component(**settings)
        elif isinstance(component, type) and issubclass(component, Model):
            component = self.transform_submodel(component)
        else:
            assert isinstance(component, Serializer)
            component = self.transform_serializer(component, settings)
        return component

    def add(self, component, *, settings=None, default_name=None):
        transformed = self.transform_component(
            component=component,
            default_name=default_name,
            settings=settings
        )
        self.push(transformed)

    def insert(self, idx, component):
        self._lock.acquire()
        self._components.insert(idx, component)
        self._lock.release()

    def discard(self, component):
        self._lock.acquire()
        try:
            idx = self._components.index(component)
        except IndexError:
            idx = None
        self._lock.release()
        if idx is not None:
            self.pop(idx)

    def push(self, component):
        self._lock.acquire()
        self._components.append(component)
        self._lock.release()

    def pop(self, index=-1) -> ComponentT | None:
        self._lock.acquire()
        obj = self._components.pop(index)
        self._lock.release()
        return obj

    def get(self, index=-1, context=None) -> ComponentT | None:
        self._lock.acquire()
        try:
            obj = self._components[index]
        except IndexError:
            obj = None
        self._lock.release()
        return obj

    def clear(self):
        self._lock.acquire()
        self._components.clear()
        self._lock.release()

    @property
    def size(self) -> int:
        return len(self._components)

    def get_final_components(self, context) -> dict[str, ComponentT]:
        final = {}
        for idx in range(self.size):
            component = self.get(idx, context)
            if component is not None:
                final[component.name] = component
        return final

    def __repr__(self):
        name = type(self).__name__
        return f'<{name} {self._components}>'


class FilteredComponentStack(ComponentStack):
    def predicate(self, component, context):
        return True

    def get(self, index=-1, context=None):
        if context is None:
            context = {}
        component = super().get(index)
        if component is None:
            return component
        if not self.predicate(component, context):
            component = None
        return component


class VersionAwareComponentStack(FilteredComponentStack):
    def __init__(
            self,
            *,
            since_field="version_added",
            until_field="version_removed",
            default_version=GREATEST,
            default_since_version=LEAST,
            default_until_version=GREATEST
    ):
        super().__init__()
        self.since_version_field = since_field
        self.until_version_field = until_field
        self.default_version = default_version
        self.default_since_version = default_since_version
        self.default_until_version = default_until_version

    def predicate_version(self, component, context):
        version = context.get("version", self.default_version)
        since_version = getattr(component, self.since_version_field, self.default_since_version)
        until_version = getattr(component, self.until_version_field, self.default_until_version)
        return since_version <= version or until_version >= version

    def predicate(self, component, context):
        return self.predicate_version(component, context)


class ComponentDescriptor:
    def __init__(self, component: ComponentT):
        self.component = component
        self.value = MISSING

    def __get__(self, instance, owner):
        if instance is not None:
            return self.value
        return self

    def __set__(self, instance, value):
        self.value = value

    def __call__(self, value):
        self.__set__(None, value)
        return value


class Model:
    descriptor_class = ComponentDescriptor

    def __init__(self, driver: Driver, serializer=None, **context):
        self.driver = driver
        serializer = serializer or driver.default_model_serializer
        if serializer is not None:
            serializer = ComponentStack.transform_serializer(serializer, context)
        self.serializer = serializer
        self._descriptors = {}
        components = self.stack.get_final_components(context)
        for key, value in components.items():
            self._descriptors[key] = self.descriptor_class(value)

    @classmethod
    def add_component(cls, component: ComponentT, default_name: str | None = None):
        cls.stack.add(
            component=component,
            default_name=default_name,
            settings=cls.settings
        )
        return cls

    @classmethod
    def discard_component(cls, component):
        cls.stack.discard(component=component)
        return cls

    @property
    def name(self):
        return type(self).__name__

    def dump(self, **context):
        return self.serializer.dump(self, context=context)

    def load(self, dump, **context):
        load = self.serializer.load(dump, context=context)
        state = self.get_state(load)
        self.set_state(state)
        return self

    @functools.singledispatchmethod
    def get_state(self, load) -> dict | tuple[tuple[str, typing.Any], ...]:
        raise TypeError(f"unsupported state type: {strings.truncate(type(load).__name__)}")

    @get_state.register
    def get_state_from_sequence(self, load: collections.abc.Sequence) -> dict:
        return dict(zip(self._descriptors, load))

    @get_state.register
    def get_state_from_mapping(self, load: collections.abc.Mapping) -> dict:
        return dict(load)

    def set_state(self, state):
        if callable(getattr(state, "items", None)):
            state = state.items()
        for item, value in state:
            self[item] = value

    def __iter__(self):
        for name in self._descriptors:
            yield name, self[name]

    def __setitem__(self, key, value):
        self._descriptors[key].__set__(self, value)

    def __getitem__(self, key):
        return self._descriptors[key].__get__(self, None)

    def __getattr__(self, key):
        return self[key]

    def __init_subclass__(
            cls,
            stack=None,
            from_members=None,
            stack_class=VersionAwareComponentStack,
            **settings
    ):
        if from_members is None:
            from_members = stack is None
        if stack is None:
            stack = stack_class()
        cls.stack = stack
        cls.settings = settings
        if from_members:
            for default_name, component in inspect.getmembers(cls):
                if isinstance(component, (Serializer, Model)):
                    cls.add_component(component, default_name=default_name)


ComponentT = typing.TypeVar("ComponentT", Serializer, Model)


def model(
        *components,
        stack=None,
        name=None,
        model_class=Model,
        stack_class=VersionAwareComponentStack,
        serializer=None,
        **settings
):
    if stack is None:
        stack = stack_class()
    for component in components:
        stack.add(component, settings=settings)
    if name is None:
        name = "model_" + str(id(stack))
    return type(name, (model_class,), {}, stack=stack, serializer=serializer)
