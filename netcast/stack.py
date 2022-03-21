from __future__ import annotations

import string
import threading
from typing import TYPE_CHECKING, Type

from netcast import GREATEST, LEAST
from netcast.tools.collections import Comparable
from netcast.tools.inspection import get_attrs
from netcast.serializer import Serializer, SettingsT

if TYPE_CHECKING:
    from netcast.model import Model, ComponentArgumentT, ComponentT


__all__ = ("Stack", "SelectiveStack", "VersionAwareStack")


class Stack:
    def __init__(
        self,
        name: str | None = None,
        default_name_template: str | string.Template = "unnamed_%(index)d",
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
            component=component,
            name=name,
            settings=settings
        )
        self.push(transformed)
        return transformed

    def insert(self, idx: int, component: ComponentT):
        self._lock.acquire()
        self._components.insert(idx, component)
        self._lock.release()

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
        if component.name is None:
            component.name = self.default_name()
        self._components.append(component)
        self._lock.release()

    def pop(self, index: int = -1) -> ComponentT | None:
        self._lock.acquire()
        obj = self._components.pop(index)
        self._lock.release()
        return obj

    def get(self, index: int = -1, settings: SettingsT = None) -> ComponentT | None:
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

    def get_suitable_components(
        self, settings: SettingsT = None
    ) -> dict[str, ComponentT]:
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
        cls, component: Serializer | Type, settings: SettingsT = None  # [Serializer],
    ) -> Serializer:
        if settings is None:
            settings = {}
        if isinstance(component, type) or getattr(component, "contained", False):
            component = component(**settings)
        component.contained = True
        for key in set(settings).intersection({"name", "default"}):
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
        self._components.clear()

    def __repr__(self) -> str:
        name = type(self).__name__
        return f"<{name} {self._components}>"


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
        since_field: str = "version_added",
        until_field: str = "version_removed",
        default_version: Comparable = GREATEST,
        default_since_version: Comparable = LEAST,
        default_until_version: Comparable = GREATEST,
        versioning_namespace: str | None = "settings",
    ):
        super().__init__()
        self.settings_version_field = settings_version_field
        self.since_version_field = since_field
        self.until_version_field = until_field
        self.default_version = default_version
        self.default_since_version = default_since_version
        self.default_until_version = default_until_version
        if versioning_namespace is None:
            versioning_namespace = ""
        self.versioning_namespace = versioning_namespace

    def predicate_version(self, component: ComponentT, settings: SettingsT):
        if settings is None:
            settings = {}
        version = settings.get(self.settings_version_field, self.default_version)
        since_version_field = f"{self.versioning_namespace}[{self.since_version_field}]"
        until_version_field = f"{self.versioning_namespace}[{self.until_version_field}]"
        if not self.versioning_namespace:
            since_version_field = since_version_field[1:-1]
            until_version_field = until_version_field[1:-1]
        default_since_version = self.default_since_version
        default_until_version = self.default_until_version
        version_added = get_attrs(component, since_version_field, None)
        if version_added is None:
            version_added = default_since_version
        version_removed = get_attrs(component, until_version_field, None)
        if version_removed is None:
            version_removed = default_until_version
        introduced = version_added <= version
        up_to_date = version_removed > version
        return introduced and up_to_date

    def predicate(self, component: ComponentT, settings: SettingsT):
        return self.predicate_version(component, settings)
