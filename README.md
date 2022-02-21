# netcast – a new approach to data serialization

<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Achtung-orange.svg/800px-Achtung-orange.svg.png" width="15" height="13"><!--
--> This library is not yet an MVP. It is not ready to be published.<!--
--></img>

## Introduction
**_netcast_** is a Python package for many purposes related to the processing of structured data.
It provides a light-weight, simple API for designing **abstract, multi-component, contextual and 
adaptable data structures**, the individual branches of which are **configurable and easily 
interchangeable**.

## Major features

### Abstraction of data structures
_netcast_ introduces an independent typing system that is roughly similar to the [Python 
data model](https://docs.python.org/3/reference/datamodel.html). With its help, you can easily 
separate fixed schemas from changing standards, thus applying the principles of 
[SOLID](https://en.wikipedia.org/wiki/SOLID), [KISS](https://en.wikipedia.org/wiki/KISS_principle) 
and [DRY](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself).

### When it comes to performance
It depends only on the used driver, i.e. the implementation dealing with 
the actual processing of the data in real time. The library itself only manages to bind components 
and put assigned values to the proper places inside them during the runtime.

### Elastic design
This is an example implementation of a data model with _netcast_.
```py
import netcast as nc


class Foo(nc.Model):
    bar = nc.String()
    baz = nc.Int()
    biz = nc.Char(unsigned=False)
    ext = nc.Int(version_added=2, default=20)


driver = nc.bin.driver()  # the default driver of the binary engine

foo = Foo(bar="bar", baz=1, biz=2, ext=3)
serializer = driver(foo)

# Dumping - returned values are :attr:`serializer.dump_type` instances (bytes)
dump_v1 = serializer.dump(version=1)  #  b"\x03bar\x00\x00\x00\x01\x02"
dump_v2 = serializer.dump()           #  b"\x03bar\x00\x00\x00\x01\x02\x00\x00\x00\x03"

# Loading - returned values are :class:`Foo` instances
loaded_v1 = serializer.load(dump_v1, version=1)
loaded_v2 = serializer.load(dump_v2)

assert loaded_v1 == Foo(bar="bar", baz=1, biz=2)  # ext=20, default
assert loaded_v2 == foo
```

#### Mutability of components
_netcast_ models are build upon special `ComponentStack` objects, which are accessible from the
`Model.stack` attribute. In the case shown above, fields `bar`, `baz`, `biz` and `ext` 
created the stack automatically thanks to the `Model` class inheritance magic inspection, 
but it is not obligatory – **dependency injection** is welcome.

This little trick allows to present the model as a list of components. Components can be either
`Serializer` or `Model` objects. You can nest models and impose custom settings on them
(like `version_added=2`), which will be propagated to all the components inside, recursively. 
Those configurations will influence serialization and deserialization of any considered _netcast_ 
data model.

#### Built-in support for backward compatibility
Having jumped to `dump_v1` assignment line, you can see the `version=1` parameter. It means 
that the context of the dumped model has `version` equal to `1`. That's why `ext` neither 
gets dumped nor loaded.

## License
[GNU General Public License v3](LICENSE)

## Contributing
**Looking for developers!**
Please feel free to contribute in any way – issues, PRs, suggestions. 

## Documentation
Not finished.

## Background
Serious development of _netcast_ started in December 2021, a few months after a few ideas
connected with parsing and building data packets came up to my mind when I had been programming
the TCP/UDP network protocol for the multiplayer game named _Jazz Jackrabbit 2_.


