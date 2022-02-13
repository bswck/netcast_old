from __future__ import annotations

import inspect
import threading
import typing

from netcast.engine import get_global_engine
from netcast.constants import LEAST, GREATEST

if typing.TYPE_CHECKING:
    from netcast import Driver


class ComponentStack:
    def __init__(self):
        self._components = []
        self._lock = threading.RLock()

    @classmethod
    def transform_submodel(cls, submodel):
        return submodel

    @classmethod
    def transform_serializer(cls, component, settings=None):
        if settings is None:
            settings = {}
        return component(**settings)

    def transform_component(self, component, *, settings=None, default_name=None):
        if isinstance(component, type) and issubclass(component, Model):
            component = self.transform_submodel(component)
        if settings is None:
            settings = {}
        settings.setdefault("name", default_name)
        if isinstance(component, type) and not issubclass(component, Model):
            component = component(**settings)
        else:
            component = self.transform_serializer(component, settings)
        return component

    def add(self, component, *, settings=None, default_name=None):
        transformed = self.transform_component(
            component=component, default_name=default_name, settings=settings
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

    def pop(self, index=-1):
        self._lock.acquire()
        obj = self._components.pop(index)
        self._lock.release()
        return obj

    def get(self, index=-1, context=None):
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
    def size(self):
        return len(self._components)

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
        if self.predicate(component, context):
            component = None
        return component


class VersionAwareComponentStack(FilteredComponentStack):
    def __init__(self, since_field="version_added", until_field="version_removed"):
        super().__init__()
        self.since_version_field = since_field
        self.until_version_field = until_field

    def predicate_version(self, component, context):
        version = context.get("version", LEAST)
        if (
            version <= getattr(component, self.since_version_field, LEAST)
            or version > getattr(component, self.until_version_field, GREATEST)
        ):
            component = None
        return component

    def predicate(self, component, context):
        return self.predicate_version(component, context)


class Model:
    def __init_subclass__(
            cls,
            stack=None,
            from_members=None,
            settings=None,
            serializer=None,
            stack_class=VersionAwareComponentStack
    ):
        if from_members is None:
            from_members = stack is None
        if stack is None:
            stack = stack_class()
        cls.stack = stack
        cls.settings = settings
        cls.serializer = serializer
        if from_members:
            for default_name, component in inspect.getmembers(cls):
                cls.add_component(component, default_name=default_name)

    def __init__(self, driver: str | Driver, engine=None):
        if engine is None:
            engine = get_global_engine()
        if isinstance(driver, str):
            driver = engine.get_driver(driver)
        self._state = driver(self).state

    def __setitem__(self, key, value):
        self._state[key] = value

    def __getitem__(self, key, value):
        return self._state[key]

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, key, value):
        return self[key]

    def dump(self):
        return self.serializer.dump(self.serializer._coerce_load_type(self._state))

    def load(self, dump):
        return self.serializer.load(self.serializer._coerce_dump_type(dump))

    @classmethod
    def add_component(cls, component, default_name=None):
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


def model(
        *components,
        stack=None,
        name=None,
        model_class=Model,
        stack_class=VersionAwareComponentStack,
        **settings
):
    if stack is None:
        stack = stack_class()
    for component in components:
        stack.add(component, settings=settings)
    if name is None:
        name = "model_" + str(id(stack))
    return type(name, (model_class,), {}, stack=stack)
