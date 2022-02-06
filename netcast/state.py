from __future__ import annotations

import dataclasses
import typing

from netcast.tools import Symbol


if typing.TYPE_CHECKING:
    from typing import Any
    from netcast import Driver, Engine


class _StateTraversible:
    def __getitem__(self, item):
        return BranchState(
            _model=self._model[item],
            _owner=self,
            _driver=self._driver
        )

    def __getattr__(self, item):
        return self[item]


@dataclasses.dataclass
class State(_StateTraversible):
    _model: Model  # noqa
    _engine: Engine
    _driver: typing.Type[Driver]


@dataclasses.dataclass
class BranchState(_StateTraversible):
    _model: Model  # noqa
    _driver: typing.Type[Driver]
    _owner: _StateTraversible
    _value: Any = Symbol("undefined")

    def set_driver(self, driver=None):
        self._driver = self._owner._engine.get_driver(driver)

    def __call__(self, value):
        self._value = value
        return self._owner
