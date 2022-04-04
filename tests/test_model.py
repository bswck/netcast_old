import netcast as nc


class TestModel:
    def test_subclass_creation(self):
        class Foo(nc.Model):
            abc = alias = nc.String()
            bar = nc.Integer

        assert Foo().name == Foo.__name__.casefold()
        assert isinstance(Foo.abc, nc.Field)
        assert Foo.abc.name == "abc"
        assert isinstance(Foo.bar, nc.Field)
        assert Foo.bar.name == "bar"
        assert isinstance(Foo.alias, nc.FieldAlias)
        assert Foo.alias.name == "abc"
        assert Foo.bar.contained
        assert Foo.stack.size == 2

        my_settings = {"setting": "value", "name": "test"}

        class Bar(nc.Model, **my_settings):
            foo = nc.List

        assert Bar().name == my_settings.pop("name")
        assert isinstance(Bar.foo, nc.Field)
        assert Bar.settings == my_settings
        assert Bar().settings == my_settings

    def test_functional_creation(self):
        model_name = "Foo"
        foo_model = nc.create_model(nc.Integer, name=model_name)

        assert foo_model().name == model_name
        assert isinstance(foo_model.f_1, nc.Field)
        assert foo_model.f_1.contained
        assert foo_model.stack.size == 1

        model_name = "bar"
        field_name = "foo"
        bar_model = nc.create_model(nc.Integer(name=field_name), name=model_name)

        assert getattr(bar_model, field_name, None) is not None
        assert isinstance(bar_model.foo, nc.Field)
        assert bar_model.foo.contained
        assert bar_model.stack.size == 1
