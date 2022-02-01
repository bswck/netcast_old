from netcast.cast.plugin import default, feature, Plugin


class AsyncSerializer(Plugin):
    async def _default_cast_async(self, load_or_dump):
        raise NotImplementedError

    _dump_async = default(_default_cast_async)
    _load_async = default(_default_cast_async)

    @feature
    async def load_async(self, dumped, context=None):
        """Cast an origin value to the cast type."""
        return await self._load_async(dumped, context=None)

    @feature
    async def dump_async(self, loaded):
        """Cast an origin value to the cast type."""
        return await self._dump_async(loaded)
