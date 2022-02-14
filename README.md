# netcast

## What is it?
**_netcast_** is a Python package for many purposes related to the processing of structured data.
It provides a light-weight, simple API for designing **abstract, multi-component, contextual and 
adaptable data structures**, the individual branches of which are **configurable and easily 
interchangeable**.

## A new approach to data serialization

### Abstraction of data structures
_netcast_ introduces an independent type system that is roughly similar to the [Python 
data model](https://docs.python.org/3/reference/datamodel.html). With its help, you can easily 
separate fixed schemas from changing standards, thus applying the principles of 
[SOLID](https://en.wikipedia.org/wiki/SOLID), [KISS](https://en.wikipedia.org/wiki/KISS_principle) 
and [DRY](https://pl.wikipedia.org/wiki/DRY).

### Performance is safe and sound
If hypothetically considering a migration, _netcast_ is guaranteed not to affect the performance 
worked-out hitherto. It depends only on the used driver, i.e. the implementation dealing with 
the actual processing of the data in real time. The library itself only manages to bind components 
and put assigned values to the proper places inside them during the runtime.


### Legible format
Let's have a look at an example implementation of a _netcast_ data model.
```py
import netcast as nc

class Foo(nc.Model):
    bar = nc.String
    baz = nc.Int64(signed=True)

```



### Variability of components – built-in support for backward compatibility
_netcast's_ `FilteredComponentStack` lets you filter particular components to be loaded or parsed
depending on the used predicate. Its subclass, `VersionAwareComponentStack` is a simple handler 
for versioned data models, which makes it possible to backward compatible its older versions.
It is of course possible to override the behaviour depending on your needs.

### 

