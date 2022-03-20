import netcast as nc


class TestModel:
    def test_subclass_creation(self):
        class Foo(nc.Model):
            abc = alias = nc.String()
            bar = nc.Integer

        assert Foo().name == Foo.__name__
        assert isinstance(Foo.abc, nc.ComponentDescriptor)
        assert Foo.abc.name == "abc"
        assert isinstance(Foo.bar, nc.ComponentDescriptor)
        assert Foo.bar.name == "bar"
        assert isinstance(Foo.alias, nc.ProxyDescriptor)
        assert Foo.alias.name == "abc"
        assert Foo.bar.contained
        assert Foo.stack.size == 2

        my_settings = {"setting": "value"}

        class Bar(nc.Model, **my_settings):
            foo = nc.List

        assert Bar().name == Bar.__name__
        assert isinstance(Bar.foo, nc.ComponentDescriptor)
        assert Bar.settings == my_settings
        assert Bar().settings == my_settings

    def test_functional_creation(self):
        model_name = "Foo"
        foo_model = nc.create_model(nc.Integer, name=model_name)

        assert foo_model().name == model_name
        assert isinstance(foo_model.unnamed_0, nc.ComponentDescriptor)
        assert foo_model.unnamed_0.contained
        assert foo_model.stack.size == 1

        model_name = "Bar"
        field_name = "foo"
        bar_model = nc.create_model(nc.Integer(name=field_name), name=model_name)

        assert getattr(bar_model, field_name, None) is not None
        assert isinstance(bar_model.foo, nc.ComponentDescriptor)
        assert bar_model.foo.contained
        assert bar_model.stack.size == 1
