import netcast as nc
from netcast.drivers.construct import driver


class Foo(nc.Model):
    baz = nc.Int64(signed=False, default=-5)
    biz = nc.Int64(version_added=1, default=3)


foo = Foo()
foo.baz(-330)
dump = foo.dump(driver, version=0)
print(foo.load(driver, dump, version=0) == foo, foo.to_state())
