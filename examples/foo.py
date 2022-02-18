import netcast as nc


class Foo(nc.Model):
    bar = nc.String()
    baz = nc.Int()
    biz = nc.Char(unsigned=False)
    ext = nc.Int(version_added=2, default=20)

#
# driver = nc.get_category("bin").get_driver()  # the default driver of the binary engine
#
# foo = Foo(bar="bar", baz=1, biz=2, ext=3)
# serializer = driver(Foo)
#
# # Dumping - returned values are :attr:`serializer.dump_type` instances (bytes)
# dump_v1 = serializer.dump(version=1)  #  b"\x03bar\x00\x00\x00\x01\x02"
# dump_v2 = serializer.dump()           #  b"\x03bar\x00\x00\x00\x01\x02\x00\x00\x00\x03"
#
# # Loading - returned values are :class:`Foo` instances
# loaded_v1 = serializer.load(dump_v1, version=1)
# loaded_v2 = serializer.load(dump_v2)
#
# assert loaded_v1 == Foo(bar="bar", baz=1, biz=2)  # ext=20, default
# assert loaded_v2 == foo
