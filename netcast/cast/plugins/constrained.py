from netcast.cast.plugin import Plugin, hook, default


class Constrained(Plugin):
    constraints = default(())

    @hook(before='dump', after='load', finalizer_takes_result=True)
    def validate_load(self, loaded):
        for constraint in self.constraints:
            constraint.validate(loaded, load=True)

    @hook(before='load', after='dump', finalizer_takes_result=True)
    def validate_dump(self, dumped):
        for constraint in self.constraints:
            constraint.validate(dumped, dump=True)

    @hook(
        before='dump_async',
        after='load_async',
        finalizer_takes_result=True,
        dependent=True
    )
    async def validate_load_async(self, loaded):
        for constraint in self.constraints:
            await constraint.validate(loaded, load=True)

    @hook(
        before='dump_async',
        after='load_async',
        finalizer_takes_result=True,
        dependent=True
    )
    async def validate_load_async(self, dumped):
        for constraint in self.constraints:
            await constraint.validate(dumped, dump=True)
