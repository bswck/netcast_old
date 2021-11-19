import construct as cs

import netcast as nc


class Packet(nc.Struct):
    header = cs.PascalString(cs.Byte, 'ascii')
    start = b'\x00'
    ints = cs.Array(10, cs.Byte)
    stop = b'\xff'


print('packet class:', Packet)
packet = Packet(header='some header', ints=range(10))
print('packet filled in:', packet)
print('packet serialized:', nc.serialize(packet))

Packet = nc.Struct(
    header=cs.PascalString(cs.Byte, 'ascii'),
    start=b'\x00',
    ints=cs.Array(10, cs.Byte),
    stop=b'\xff'
)

print()
print('packet class:', Packet)
packet = Packet(header='some header', ints=range(10))
print('packet filled in:', packet)
print('packet serialized:', nc.serialize(packet))
