from __future__ import annotations

import io

import construct
import netcast


__driver_name__ = "construct"


class RealAdapter(netcast.Adapter, netcast.Real, config=True):
    def _get_swapped(self):
        if self.big is None and self.native is None and self.little is not None:
            return self.little
        if self.big is None and self.native is not None:
            return self.native
        return True if self.big is None else self.big

    def _get_bi(self, *, signed):
        byte_length = self.bit_length >> 3
        return construct.BytesInteger(byte_length, signed=signed, swapped=self._get_swapped())

    def _get_ff(self, *, signed):
        type_name = "Int" if self.__load_type__ is int else "Float"
        type_name += str(self.bit_length)
        type_name += ("s" if signed else "u") if self.__load_type__ is int else ""

        if self.big:
            type_name += "b"
        elif self.little:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj

    def setup(self):
        obj = self.get("impl")

        if obj is not None:
            return

        big = self.setdefault("big", None)
        little = self.setdefault("little", None)
        native = self.setdefault("native", None)
        cpu_sized = self.setdefault("cpu_sized", True)
        signed = self.bounds[0]

        if cpu_sized and any(map(callable, (big, little, native))):
            self.cfg.cpu_sized = cpu_sized = False

        if cpu_sized:
            obj = self._get_ff(signed=signed)

        if obj is None:
            obj = self._get_bi(signed=signed)

        if obj is None:
            raise ImportError(f"construct does not support {self.__visit_key__}")

        self.cfg.impl = obj

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
            path=f"(parsing {type(self).__name__} using netcast)",
        )

    def _dump(self, loaded, context=None, stream=None, **_kwargs):
        stream = self.ensure_stream(stream)
        self.impl._build(
            obj=loaded,
            stream=stream,
            context=context,
            path=f"(building {type(self).__name__} using netcast)",
        )
        offset = stream.tell() - self.impl.length  # noqa
        stream.seek(offset)
        dumped = stream.read()
        return dumped


class ConstructDriver(netcast.Driver):
    Real = netcast.serializer_factory(RealAdapter)

    SignedInt8 = Real(netcast.SignedInt8)
    SignedInt16 = Real(netcast.SignedInt16)
    SignedInt32 = Real(netcast.SignedInt32)
    SignedInt64 = Real(netcast.SignedInt64)
    SignedInt128 = Real(netcast.SignedInt128)
    SignedInt256 = Real(netcast.SignedInt256)
    SignedInt512 = Real(netcast.SignedInt512)
    UnsignedInt8 = Real(netcast.UnsignedInt8)
    UnsignedInt16 = Real(netcast.UnsignedInt16)
    UnsignedInt32 = Real(netcast.UnsignedInt32)
    UnsignedInt64 = Real(netcast.UnsignedInt64)
    UnsignedInt128 = Real(netcast.UnsignedInt128)
    UnsignedInt256 = Real(netcast.UnsignedInt256)
    Float16 = Real(netcast.Float16)
    Float32 = Real(netcast.Float32)
    Float64 = Real(netcast.Float64)


ncd = ConstructDriver
typ = ncd.UnsignedInt32(policy='reshape')
print(typ.dump(-10))
