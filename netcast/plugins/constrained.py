from __future__ import annotations

from netcast.constraints import Constraint
from netcast.plugin import Plugin, hook, default
from netcast.tools import Params


class Constrained(Plugin):
    constraints: tuple[Constraint, ...] = default(())

    @hook(
        call_before="dump",
        call_after="load",
        finalizer_takes_result=True,
        precedential_reshaping=True,
    )
    def validate_load(self, loaded):
        for constraint in self.constraints:
            loaded = constraint.validate(loaded, load=True)
        return Params.frame(loaded)

    @hook(
        call_before="load",
        call_after="dump",
        finalizer_takes_result=True,
        precedential_reshaping=True,
    )
    def validate_dump(self, dumped):
        for constraint in self.constraints:
            dumped = constraint.validate(dumped, dump=True)
        return Params.frame(dumped)

    @hook(
        call_before="dump_async",
        call_after="load_async",
        finalizer_takes_result=True,
        precedential_reshaping=True,
        is_dependent=True,
    )
    async def validate_load_async(self, loaded):
        for constraint in self.constraints:
            loaded = await constraint.validate(loaded, load=True)
        return Params.frame(loaded)

    @hook(
        call_before="load_async",
        call_after="dump_async",
        finalizer_takes_result=True,
        precedential_reshaping=True,
        is_dependent=True,
    )
    async def validate_dump_async(self, dumped):
        for constraint in self.constraints:
            dumped = await constraint.validate(dumped, dump=True)
        return Params.frame(dumped)
