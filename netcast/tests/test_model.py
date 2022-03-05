import netcast as nc


class TestModel:
    def test_subclass(self):
        class Foo(nc.Model):
            abc = alias = nc.String
            bar = nc.Integer

        assert isinstance(Foo.abc, nc.ComponentDescriptor)
        assert isinstance(Foo.bar, nc.ComponentDescriptor)
        assert isinstance(Foo.alias, nc.AliasDescriptor)
        assert Foo.bar.taken
        assert Foo.stack.size == 2

    def test_funcapi(self):
        Foo = nc.model(nc.Integer, name="Foo")

        assert isinstance(Foo.field_0, nc.ComponentDescriptor)
        assert Foo.field_0.taken
        assert Foo.stack.size == 1
