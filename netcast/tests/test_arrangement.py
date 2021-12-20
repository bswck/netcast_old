from typing import ClassVar, Type

import pytest

from netcast.arrangement import ClassArrangement, Arrangement
from netcast.context import Context, DictContext, ListContext

class_arrangement_subclasses = [ClassArrangement, *ClassArrangement.__subclasses__()]
class_arrangement_subclasses.remove(Arrangement)
arrangement_subclasses = [Arrangement, *Arrangement.__subclasses__()]


@pytest.fixture(params=class_arrangement_subclasses)
def ca(request):
    yield request.param


@pytest.fixture(params=arrangement_subclasses)
def a(request):
    yield request.param


class TestClassArrangement:
    def test_abstract(self):
        with pytest.warns(UserWarning):
            class Abstract(ClassArrangement, abstract=True):
                context_class = ListContext

                def test(self):
                    assert self.context is None

        class CA1(ClassArrangement, descent=Abstract):
            # using descent= here is pointless; 
            # just testing if all things behave fine
            def test(self):
                assert isinstance(self.context, dict)  # we don't want list here

        class CA2(Abstract):
            # using descent= here is pointless;
            # just testing if all things behave fine
            def test(self):
                CA1.test(self)  # type: ignore  # we don't want list here

        class CA3(Abstract):
            context_class = ListContext

            def test(self):
                assert isinstance(self.context, list)  # we want list here

        CA1().test()
        CA2().test()
        CA3().test()

    def test_descent(self, ca):
        class CA1(ca):
            pass

        class CA2(CA1):
            def test(self):
                assert self.descent_type is None  # how could I know?
                assert self.context is CA1.get_context()

        class CA3(CA1, descent=CA1):  # this one's interesting.
            def test(self):
                assert self.descent_type is CA1
                assert self.context is CA1.get_context()

        class CA4(ca, descent=CA1):
            def test(self):
                assert self.descent_type is CA1
                assert self.context is CA2.get_context()

        CA2().test()
        CA3().test()
        CA4().test()

    def test_inherit_context(self, ca):
        class CA1(ca):
            def test(self):
                assert self.supercontext is None

        class CA2(ca, descent=CA1):
            inherit_context = False

            def test(self):
                assert self.supercontext is CA1.get_context()
                assert self.context is CA2.get_context()

        class CA3(ca, descent=CA1):
            inherit_context = None  # default one

            def test(self):
                assert self.context is CA1.get_context()

        class CA4(ca, descent=CA3):
            inherit_context = False

            def test(self):
                assert self.supercontext is CA3.get_context() is CA1.get_context()
                assert self.context is CA4.get_context()

        class CA5(ca, descent=CA4):
            def test(self):
                CA4.test(self)

        class CA6(ca, descent=CA5):
            inherit_context = False

            def test(self):
                assert self.supercontext is CA5.get_context()
                assert self.context is CA6.get_context()

        CA1().test()
        CA2().test()
        CA3().test()
        CA4().test()
        CA5().test()
        CA6().test()

    def test_context_type(self, ca):
        class TypeTester:
            context: Context
            context_class: ClassVar[Type[Context]]

            def test(self):
                if ca.context_class is None:
                    expected_context_class = DictContext
                else:
                    expected_context_class = ca.context_class
                assert type(self.context) is expected_context_class is self.context_class

        class CA1(ca, TypeTester):
            pass

        class CA2(ca, TypeTester, descent=CA1):
            inherit_context = False

        CA1().test()
        CA2().test()
