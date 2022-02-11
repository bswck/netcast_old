from __future__ import annotations

import dataclasses
import functools
import typing


from netcast.constants import MISSING

if typing.TYPE_CHECKING:
    from typing import Any
    from netcast import Driver, Engine


class _StateTraversable:
    @functools.lru_cache
    def __getitem__(self, item):
        return BranchState(
            model=self._model[item],
            owner=self,
            driver=self._driver
        )

    def __getattr__(self, item):
        return self[item]


@dataclasses.dataclass
class State(_StateTraversable):
    model: Model  # noqa
    engine: Engine
    driver: typing.Type[Driver]


@dataclasses.dataclass
class BranchState(_StateTraversable):
    model: Model  # noqa
    driver: typing.Type[Driver]
    owner: _StateTraversable
    _value: Any = MISSING

    def set_driver(self, driver=None):
        self.driver = self.owner.engine.get_driver(driver)

    def __call__(self, value):
        self._value = value
        return self.owner
