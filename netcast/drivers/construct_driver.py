from __future__ import annotations

import io
from typing import TypeVar

import construct
import netcast

from netcast.tools.symbol import Symbol


__driver_name__ = 'construct'


class NumberSerializer(netcast.DriverSerializer, netcast.Real, config=True):
    _impl: construct.Construct

    @property
    def impl(self):
        return self._impl

    def setup(self):
        self.cfg.setdefault('big', True)
        self.cfg.setdefault('little', False)
        self.cfg.setdefault('native', False)
        self.cfg.setdefault('use_ff', True)

        signed = self.bounds[0]
        obj = missing = Symbol()

        if (
            self.cfg.use_ff
            and any(map(callable, (self.cfg.big, self.cfg.little, self.cfg.native)))
        ):
            self.cfg.use_ff = False

        if self.cfg.use_ff:
            type_name = 'Int' if self.__load_type__ is int else 'Float'
            type_name += str(self.bit_length)
            type_name += ('s' if signed else 'u') if self.__load_type__ is int else ''

            if self.cfg.big:
                type_name += 'b'
            elif self.cfg.little:
                type_name += 'l'
            else:
                type_name += 'n'
            obj = getattr(construct, type_name, missing)

        if obj is missing:
            length = self.bit_length // 8
            obj = construct.BytesInteger(length, signed=signed, swapped=self.cfg.little)

        if obj is missing:
            raise ImportError(f'construct does not support {self.__visit_key__}')

        self._impl = obj

    @staticmethod
    def ensure_stream(dumped):
        if isinstance(dumped, io.BytesIO):
            return dumped
        if dumped:
            return io.BytesIO(dumped)
        return io.BytesIO()

    def _load(self, dumped, context=None, **_kwargs):
        return self.impl._parse(
            stream=self.ensure_stream(dumped),
            context=context,
            path=f'(parsing {type(self).__name__} using a netcast driver)'
        )

    def _dump(self, loaded, context=None, stream=None, **_kwargs):
        stream = self.ensure_stream(stream)
        self.impl._build(
            obj=loaded,
            stream=stream,
            context=context,
            path=f'(building {type(self).__name__} using a netcast driver)'
        )
        offset = stream.tell() - self.impl.length  # noqa
        stream.seek(offset)
        dumped = stream.read()
        return dumped


ST = TypeVar('ST')


def number(serializer: ST) -> ST:
    return netcast.serializer_impl(serializer, adapter=NumberSerializer)


class ConstructDriver(netcast.Driver):
    SignedInt8 = number(netcast.SignedInt8)
    SignedInt16 = number(netcast.SignedInt16)
    SignedInt32 = number(netcast.SignedInt32)
    SignedInt64 = number(netcast.SignedInt64)
    SignedInt128 = number(netcast.SignedInt128)
    SignedInt256 = number(netcast.SignedInt256)
    SignedInt512 = number(netcast.SignedInt512)
    UnsignedInt8 = number(netcast.UnsignedInt8)
    UnsignedInt16 = number(netcast.UnsignedInt16)
    UnsignedInt32 = number(netcast.UnsignedInt32)
    UnsignedInt64 = number(netcast.UnsignedInt64)
    UnsignedInt128 = number(netcast.UnsignedInt128)
    UnsignedInt256 = number(netcast.UnsignedInt256)
    Float16 = number(netcast.Float16)
    Float32 = number(netcast.Float32)
    Float64 = number(netcast.Float64)

    # Class-level boilerplate gens accessors
    number = staticmethod(number)
