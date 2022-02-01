from __future__ import annotations

import functools
import io

import construct
import netcast


__driver_name__ = 'construct'


class RealSerializer(netcast.DriverSerializer):
    def setup(self):
        self.cfg.setdefault('big', True)
        self.cfg.setdefault('little', False)
        self.cfg.setdefault('native', False)

    @property
    def impl(self: netcast.Real) -> construct.Construct:
        type_name = 'Int' if self.__load_type__ is int else 'Float'
        type_name += str(self.bit_length)
        type_name += 's' if self.bounds[0] else 'u'

        if self.cfg.big:
            type_name += 'b'
        elif self.cfg.little:
            type_name += 'l'
        else:
            type_name += 'n'

        missing = netcast.Symbol()
        obj = getattr(construct, type_name, missing)
        if obj is missing:
            raise ImportError(f'construct does not support {type_name}')
        return obj

    @staticmethod
    def ensure_stream(dumped):
        if isinstance(dumped, io.BytesIO):
            return dumped
        return io.BytesIO(dumped)

    def load(self, dumped, context=None):
        return self.impl._parse(self.ensure_stream(dumped), context=context, path='(parsing)')

    def dump(self, loaded, context=None, stream=None):
        if stream is None:
            stream = io.BytesIO()
        return self.impl._build(loaded, stream, context=context, path='(building)')


impl = functools.partial(netcast.serializer_impl, adapter=RealSerializer)


class ConstructDriver(netcast.Driver):
    SignedInt8 = impl(netcast.SignedInt8)
    SignedInt16 = impl(netcast.SignedInt16)
    SignedInt32 = impl(netcast.SignedInt32)
    SignedInt64 = impl(netcast.SignedInt64)
    SignedInt128 = impl(netcast.SignedInt128)
    SignedInt256 = impl(netcast.SignedInt256)
    SignedInt512 = impl(netcast.SignedInt512)
    UnsignedInt8 = impl(netcast.UnsignedInt8)
    UnsignedInt16 = impl(netcast.UnsignedInt16)
    UnsignedInt32 = impl(netcast.UnsignedInt32)
    UnsignedInt64 = impl(netcast.UnsignedInt64)
    UnsignedInt128 = impl(netcast.UnsignedInt128)
    UnsignedInt256 = impl(netcast.UnsignedInt256)
    Float16 = impl(netcast.Float16)
    Float32 = impl(netcast.Float32)
    Float64 = impl(netcast.Float64)
