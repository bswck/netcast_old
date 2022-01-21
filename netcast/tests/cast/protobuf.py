import construct
import time
from netcast.tests.cast.protobuf_test_pb2 import Person

person_pb = Person()
person_pb.id = 1234
person_pb.name = "John Doe"
person_pb.email = "jdoe@example.com"
phone = person_pb.phones.add()
phone.number = "555-4321"
phone.type = Person.HOME

start = time.perf_counter()
print('protobuf')
print('--------')
print(person_pb.SerializeToString())
print(f'elapsed in {time.perf_counter() - start:.10f}')

person_cs = construct.Struct(
    construct.Const(b'\n'),
    name=construct.PascalString(construct.Byte, 'ascii'),
    id=construct.Int32sn,
    email=construct.PascalString(construct.Byte, 'ascii'),
    phones=construct.GreedyRange(
        construct.Struct(
            construct.Const(b'\n'),
            number=construct.PascalString(construct.Byte, 'ascii'),
            type=construct.Enum(construct.Byte, MOBILE=0, HOME=1, WORK=2),
        )
    )
)

start = time.perf_counter()
print()
print('construct')
print('---------')
print(person_cs.build(
    {'id': 1234, 'name': 'John Doe', 'email': 'jdoe@example.com', 'phones': [{'number': '555-4321', 'type': 1}]}
))
print(f'elapsed in {time.perf_counter() - start:.10f}')
