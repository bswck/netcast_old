import netcast as nc


class TestModel:
    def test_subclass_creation(self):
        class Foo(nc.Model):
            abc = alias = nc.String
            bar = nc.Integer

        assert Foo().name == Foo.__name__
        assert isinstance(Foo.abc, nc.ComponentDescriptor)
        assert isinstance(Foo.bar, nc.ComponentDescriptor)
        assert isinstance(Foo.alias, nc.AliasDescriptor)
        assert Foo.bar.contained
        assert Foo.stack.size == 2

        class Bar(nc.Model):
            foo = nc.List

        assert Foo().name == Foo.__name__
        assert isinstance(Foo.abc, nc.ComponentDescriptor)
        assert isinstance(Foo.bar, nc.ComponentDescriptor)
        assert isinstance(Foo.alias, nc.AliasDescriptor)
        assert Foo.bar.contained
        assert Foo.stack.size == 2

    def test_functional_creation(self):
        model_name = "Foo"
        foo_model = nc.model(nc.Integer, name=model_name)

        assert foo_model().name == model_name
        assert isinstance(foo_model.unnamed_0, nc.ComponentDescriptor)
        assert foo_model.unnamed_0.contained
        assert foo_model.stack.size == 1

        model_name = "Bar"
        field_name = "foo"
        bar_model = nc.model(nc.Integer(name=field_name), name=model_name)

        assert getattr(bar_model, field_name, None) is not None
        assert isinstance(bar_model.foo, nc.ComponentDescriptor)
        assert bar_model.foo.contained
        assert bar_model.stack.size == 1
