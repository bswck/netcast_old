from __future__ import annotations

import functools
import heapq
import operator
import string
import threading
import typing
from typing import Callable, Type

from netcast import GREATEST, LEAST
from netcast.tools.collections import Comparable
from netcast.serializer import Serializer, SettingsT

if typing.TYPE_CHECKING:
    from netcast.model import Model, ComponentArgumentT, ComponentT


__all__ = ("Stack", "SelectiveStack", "VersionAwareStack")


@functools.total_ordering
class _PrioritySortWrapper:
    def __init__(self, component):
        self.component = component

    def __eq__(self, other: _PrioritySortWrapper) -> bool:
        return self.component.priority == other.component.priority

    def __lt__(self, other: _PrioritySortWrapper) -> bool:
        return self.component.priority < other.component.priority


class Stack:
    def __init__(
        self,
        name: str | None = None,
        default_name_template: str | string.Template = "f_%(index)d",
    ):
        if name is None:
            name = f"{type(self).__name__.casefold()}_{id(self)}"
        self.name = name
        self.default_name_template = default_name_template
        self._components = []
        self._lock = threading.RLock()

    def add(
        self,
        component: ComponentArgumentT,
        *,
        settings: SettingsT = None,
        name: str | None = None,
    ):
        """Push with transform."""
        if isinstance(settings, dict):
            settings = settings.copy()
        transformed = self.transform_component(
            component=component, name=name, settings=settings
        )
        self.push(transformed)
        return transformed

    def all(self):
        return self._components.copy()

    def discard(self, component: ComponentT):
        self._lock.acquire()
        try:
            idx = self._components.index(component)
        except IndexError:
            idx = None
        self._lock.release()
        if idx is not None:
            self.pop(idx)

    def default_name(self):
        fmt = {"name": self.name, "index": len(self._components) + 1}
        template = self.default_name_template
        if isinstance(template, str):
            name = template % fmt  # may raise a KeyError
        elif isinstance(template, string.Template):
            name = template.substitute(fmt)  # may raise a KeyError
        else:
            raise TypeError(f"cannot format type {type(template).__name__}")
        return name

    def push(self, component: ComponentT):
        self._lock.acquire()
        name = getattr(component, "name", None)
        if name is None:
            component.name = self.default_name()
        heapq.heappush(self._components, _PrioritySortWrapper(component))
        self._lock.release()

    def pop(self, index: int | None = None) -> ComponentT | None:
        self._lock.acquire()
        if index is None:
            obj = heapq.heappop(self._components)
        else:
            obj = self._components.pop(index)
        self._lock.release()
        return obj

    def get(self, index: int = -1, settings: SettingsT = None) -> ComponentT | None:
        self._lock.acquire()
        try:
            obj = self._components[index].component
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

    def choose_components(self, settings: SettingsT = None) -> dict[str, ComponentT]:
        if settings is None:
            settings = {}
        suitable = {}
        for idx in range(self.size):
            component = self.get(idx, settings)
            if component is not None:
                suitable[component.name] = component
        return suitable

    @classmethod
    def transform_submodel(cls, submodel: Type[Model]) -> Type[Model]:
        return submodel

    @classmethod
    def transform_serializer(
        cls, component: Serializer | Type, settings: SettingsT = None
    ) -> Serializer:
        if settings is None:
            settings = {}
        if isinstance(component, type) or getattr(component, "contained", False):
            component = component(**settings)
        component.contained = True
        for key in settings.keys() & {"name", "default"}:
            setattr(component, key, settings.pop(key))
        component.settings.update(settings)
        return component

    def transform_component(
        self,
        component: ComponentArgumentT,
        *,
        settings: SettingsT = None,
        name: str | None = None,
    ) -> ComponentT | None:
        from netcast.model import Model

        if settings is None:
            settings = {}
        if name:
            settings.setdefault("name", name)
        if isinstance(component, type) and not issubclass(component, Model):
            component = self.transform_serializer(component, settings=settings)
        elif isinstance(component, type) and issubclass(component, Model):
            component = self.transform_submodel(component)
        else:
            component = self.transform_serializer(component, settings=settings)
        return component

    def __del__(self):
        for component in self._components:
            component.contained = False
        self.clear()

    def __repr__(self) -> str:
        name = type(self).__name__
        components = list(map(operator.attrgetter("component"), self._components))
        return f"<{name} {components}>"


class SelectiveStack(Stack):
    def predicate(self, component, settings: SettingsT):
        return True

    def get(self, index: int = -1, settings: SettingsT = None):
        component = super().get(index, settings)
        if component is None:
            return component
        if not self.predicate(component, settings):
            component = None
        return component


class VersionAwareStack(SelectiveStack):
    """
    A very simple and basic versioning layer.  `foo = Int64(version_added=1, version_removed=5)`
    will inform the model to include `foo` component only if `1 <= <version> < 5`.
    """

    def __init__(
        self,
        *,
        settings_version_field: str = "version",
        version_added_field: str | Callable = (
            lambda component: component.settings.get("version_added")
        ),
        version_removed_field: str | Callable = (
            lambda component: component.settings.get("version_removed")
        ),
        default_version: Comparable = GREATEST,
        default_version_added: Comparable = LEAST,
        default_version_removed: Comparable = GREATEST,
    ):
        super().__init__()
        self.settings_version_field = settings_version_field
        self.version_added_field = version_added_field
        self.version_removed_field = version_removed_field
        self.default_version = default_version
        self.default_version_added = default_version_added
        self.default_version_removed = default_version_removed

    def predicate_version(self, component: ComponentT, settings: SettingsT):
        if settings is None:
            settings = {}
        version = settings.get(self.settings_version_field, self.default_version)
        default_added = self.default_version_added
        default_removed = self.default_version_removed
        if callable(self.version_added_field):
            version_added = self.version_added_field(component)
        else:
            version_added = getattr(component, self.version_added_field, None)
        if version_added is None:
            version_added = default_added
        if callable(self.version_added_field):
            version_removed = self.version_removed_field(component)
        else:
            version_removed = getattr(component, self.version_removed_field, None)
        if version_removed is None:
            version_removed = default_removed
        introduced = version_added <= version
        up_to_date = version_removed > version
        return introduced and up_to_date

    def predicate(self, component: ComponentT, settings: SettingsT):
        return self.predicate_version(component, settings)
