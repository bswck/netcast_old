from netcast.plugin import export, Plugin


class AsyncSerializer(Plugin):
    @export
    async def load_async(self, dumped, **kwargs):
        """Cast an origin value to the cast type."""
        try:
            load_async = getattr(self, '_load_async')
        except AttributeError:
            raise NotImplementedError
        else:
            return await load_async(dumped, **kwargs)

    @export
    async def dump_async(self, loaded, **kwargs):
        """Cast an origin value to the cast type."""
        try:
            dump_async = getattr(self, '_dump_async')
        except AttributeError:
            raise NotImplementedError
        else:
            return await dump_async(loaded, **kwargs)
