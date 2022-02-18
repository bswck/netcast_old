import netcast as nc
from netcast.drivers.construct import driver


class Foo(nc.Model):
    baz = nc.Int64(default=-5)
    biz = nc.Int64(version_added=1, default=3, big_endian=True)


if __name__ == '__main__':
    foo = Foo(baz=-1, biz=5)
    print(foo.dump(driver, version=0))
