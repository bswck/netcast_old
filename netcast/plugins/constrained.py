from __future__ import annotations

from netcast.constraints import Constraint
from netcast.plugin import Plugin, export, default


class Constrained(Plugin):
    _constraints: tuple[Constraint, ...] = default(())

    def _propagate_policy(self, constraints):
        for constraint in constraints:
            constraint.policy = self.cfg.get('constraint_policy')

    @property
    def constraints(self):
        self._propagate_policy(self._constraints)
        return self._constraints

    @export(
        call_before="dump",
        call_after="load",
        communicate=True,
        initial_shaping=True,
    )
    def validate_load(self, load):
        for constraint in self.constraints:
            load = constraint.validate(load, load=True)
        return (load,), {}

    @export(
        call_before="load",
        call_after="dump",
        communicate=True,
        initial_shaping=True,
    )
    def validate_dump(self, dump):
        for constraint in self.constraints:
            dump = constraint.validate(dump, dump=True)
        return (dump,), {}

    @export(
        call_before="dump_async",
        call_after="load_async",
        communicate=True,
        initial_shaping=True,
        is_dependent=True,
    )
    async def validate_load_async(self, load):
        for constraint in self.constraints:
            load = await constraint.validate(load, load=True)
        return (load,), {}

    @export(
        call_before="load_async",
        call_after="dump_async",
        communicate=True,
        initial_shaping=True,
        is_dependent=True,
    )
    async def validate_dump_async(self, dump):
        for constraint in self.constraints:
            dump = await constraint.validate(dump, dump=True)
        return (dump,), {}
