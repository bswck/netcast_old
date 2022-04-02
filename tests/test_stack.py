import random
from typing import Type

import pytest

from netcast.stack import Stack, SelectiveStack, VersionAwareStack
from netcast.serializers import FloatingPoint, Integer, String


SERIALIZER_CLASSES = (FloatingPoint, Integer, String)


@pytest.fixture(params=SERIALIZER_CLASSES)
def serializer_class(request):
    return request.param


@pytest.fixture
def serializer(serializer_class):
    return serializer_class()


@pytest.fixture(params=(Stack, SelectiveStack, VersionAwareStack))
def stack_class(request) -> Type[Stack]:
    return request.param


@pytest.fixture
def stack(stack_class) -> Stack:
    return stack_class()


class TestStack:
    """Generic, abstract test that must succeed for all valid component stack implementations."""

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

    @pytest.mark.parametrize(
        "components", [[component() for component in SERIALIZER_CLASSES]]
    )
    @pytest.mark.parametrize("mock", [component() for component in SERIALIZER_CLASSES])
    def test_insert(self, stack, components, mock):
        for component in components:
            stack.add(component)
        offset = random.randint(0, stack.size - 1)
        stack.insert(offset, mock)
        assert stack.get(offset) is mock


class TestVersionAwareStack:
    def duplex_factory(self, serializer, version_added=None, version_removed=None):
        stack = VersionAwareStack()
        component = serializer(version_added=version_added, version_removed=version_removed)
        stack.add(component)
        return stack, component

    @pytest.mark.parametrize(
        "compatible_version, incompatible_version, version_added, version_removed",
        [
            (1, 0, 1, None),
            (0, 1, None, 1),
            (2, 1, 1.5, 2.5),
            ("c", "f", "b", "e"),
            ((1, "alpha"), (2, "alpha"), (1, "alpha"), (1, "beta")),
        ],
    )
    def test(
        self,
        serializer,
        compatible_version,
        incompatible_version,
        version_added,
        version_removed,
    ):
        stack, component = self.duplex_factory(
            serializer=serializer,
            version_added=version_added,
            version_removed=version_removed,
        )
        settings = {stack.settings_version_field: compatible_version}

        assert stack.predicate(component, settings=settings)
        assert stack.get(settings=settings) is not None

        settings[stack.settings_version_field] = incompatible_version
        assert not stack.predicate(component, settings=settings)
        assert stack.get(settings=settings) is None
