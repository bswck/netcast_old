import functools


@functools.singledispatch
def object_array_name(_cls: type, name: str, size: int) -> str:
    return str(size) + "x_" + name


@functools.singledispatch
def numbered_object_name(_cls: type, name: str, number: int) -> str:
    return name + "_" + str(number)
