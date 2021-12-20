from typing import ClassVar, Type

import pytest

from netcast.arrangement import ClassArrangement, Arrangement
from netcast.context import Context, DictContext

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
    def test_descent(self, ca):
        class CA1(ca):
            pass

        class CA2(CA1):
            def test(self):
                assert self.descent_type is None
                assert self.context is CA1.get_context()

        class CA3(ca, descent=CA1):
            def test(self):
                assert self.descent_type is CA1
                assert self.context is CA2.get_context()

        CA2().test()
        CA3().test()

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
