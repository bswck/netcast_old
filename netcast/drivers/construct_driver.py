from __future__ import annotations

import io
from typing import TypeVar

import construct
import netcast

from netcast.toolkit.symbol import Symbol


__driver_name__ = 'construct'


class NumberSerializer(netcast.DriverSerializer, netcast.Real, config=True):
    _impl: construct.Construct

    def setup(self):
        self.cfg.setdefault('big', True)
        self.cfg.setdefault('little', False)
        self.cfg.setdefault('native', False)
        type_name = 'Int' if self.__load_type__ is int else 'Float'
        type_name += str(self.bit_length)
        type_name += ('s' if self.bounds[0] else 'u') if self.__load_type__ is int else ''

        if self.cfg.big:
            type_name += 'b'
        elif self.cfg.little:
            type_name += 'l'
        else:
            type_name += 'n'

        missing = Symbol()
        obj = getattr(construct, type_name, missing)
        if obj is missing:
            raise ImportError(f'construct does not support {type_name}')
        self._impl = obj

    @property
    def impl(self):
        return self._impl

    @staticmethod
    def ensure_stream(dumped):
        if isinstance(dumped, io.BytesIO):
            return dumped
        if dumped:
            return io.BytesIO(dumped)
        return io.BytesIO()

    def _load(self, dumped, context=None, **kwargs):
        return self.impl._parse(
            stream=self.ensure_stream(dumped),
            context=context,
            path=f'(loading {type(self).__name__} using netcast)'
        )

    def _dump(self, loaded, context=None, stream=None, **kwargs):
        stream = self.ensure_stream(stream)
        self.impl._build(
            obj=loaded,
            stream=stream,
            context=context,
            path=f'(dumping {type(self).__name__} using netcast)'
        )
        offset = stream.tell() - self.impl.length  # noqa
        stream.seek(offset)
        dumped = stream.read()
        return dumped


ST = TypeVar('ST')


def num_impl(serializer: ST) -> ST:
    return netcast.serializer_impl(serializer, adapter=NumberSerializer)


class ConstructDriver(netcast.Driver):
    SignedInt8 = num_impl(netcast.SignedInt8)
    SignedInt16 = num_impl(netcast.SignedInt16)
    SignedInt32 = num_impl(netcast.SignedInt32)
    SignedInt64 = num_impl(netcast.SignedInt64)
    SignedInt128 = num_impl(netcast.SignedInt128)
    SignedInt256 = num_impl(netcast.SignedInt256)
    SignedInt512 = num_impl(netcast.SignedInt512)
    UnsignedInt8 = num_impl(netcast.UnsignedInt8)
    UnsignedInt16 = num_impl(netcast.UnsignedInt16)
    UnsignedInt32 = num_impl(netcast.UnsignedInt32)
    UnsignedInt64 = num_impl(netcast.UnsignedInt64)
    UnsignedInt128 = num_impl(netcast.UnsignedInt128)
    UnsignedInt256 = num_impl(netcast.UnsignedInt256)
    Float16 = num_impl(netcast.Float16)
    Float32 = num_impl(netcast.Float32)
    Float64 = num_impl(netcast.Float64)
