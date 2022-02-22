import random
from typing import Type

import pytest

from netcast.stack import ComponentStack, FilteredComponentStack, VersionAwareComponentStack
from netcast.serializers import FloatingPoint, Integer, String


SERIALIZER_CLASSES = (FloatingPoint, Integer, String)


@pytest.fixture(params=SERIALIZER_CLASSES)
def serializer_class(request):
    return request.param


@pytest.fixture
def serializer(serializer_class):
    return serializer_class()


@pytest.fixture(params=(ComponentStack, FilteredComponentStack, VersionAwareComponentStack))
def stack_class(request) -> Type[ComponentStack]:
    return request.param


@pytest.fixture
def stack(stack_class) -> ComponentStack:
    return stack_class()


class TestComponentStack:
    """Generic, abstract test for all valid component stack implementations."""

    def test_init(self, stack_class):
        assert stack_class()
        assert stack_class().size == 0

    def test_get(self, stack, serializer):
        stack.push(serializer)
        assert stack.get()

    def test_pop(self, stack, serializer):
        stack.push(serializer)
        assert stack.pop()
        with pytest.raises(IndexError):
            stack.pop()

    def test_add(self, stack, serializer_class):
        stack.add(serializer_class)
        assert stack.pop() is not serializer_class

    def test_transform(self, stack, serializer_class):
        component = stack.transform_component(serializer_class)
        assert component is not serializer_class

    @pytest.mark.parametrize("components", [[component() for component in SERIALIZER_CLASSES]])
    @pytest.mark.parametrize("mock", [component() for component in SERIALIZER_CLASSES])
    def test_insert(self, stack, components, mock):
        for component in components:
            stack.add(component)
        offset = random.randint(0, stack.size - 1)
        stack.insert(offset, mock)
        assert stack.get(offset) is mock
