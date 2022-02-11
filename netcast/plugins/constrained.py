from __future__ import annotations

from netcast.constraints import Constraint
from netcast.plugin import Plugin, hook, default
from netcast.tools import Params


class Constrained(Plugin):
    _constraints: tuple[Constraint, ...] = default(())
    constraint_policy = 'strict'

    def _propagate_policy(self, constraints):
        for constraint in constraints:
            constraint.policy = self.constraint_policy

    @property
    def constraints(self):
        self._propagate_policy(self._constraints)
        return self._constraints

    @hook(
        call_before="dump",
        call_after="load",
        finalizer_takes_result=True,
        precedential_reshaping=True,
    )
    def validate_load(self, load):
        for constraint in self.constraints:
            load = constraint.validate(load, load=True)
        return Params((load,))

    @hook(
        call_before="load",
        call_after="dump",
        finalizer_takes_result=True,
        precedential_reshaping=True,
    )
    def validate_dump(self, dump):
        for constraint in self.constraints:
            dump = constraint.validate(dump, dump=True)
        return Params((dump,))

    @hook(
        call_before="dump_async",
        call_after="load_async",
        finalizer_takes_result=True,
        precedential_reshaping=True,
        is_dependent=True,
    )
    async def validate_load_async(self, load):
        for constraint in self.constraints:
            load = await constraint.validate(load, load=True)
        return Params((load,))

    @hook(
        call_before="load_async",
        call_after="dump_async",
        finalizer_takes_result=True,
        precedential_reshaping=True,
        is_dependent=True,
    )
    async def validate_dump_async(self, dump):
        for constraint in self.constraints:
            dump = await constraint.validate(dump, dump=True)
        return Params((dump,))
