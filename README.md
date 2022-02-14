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

### Performance - cards on the table
_netcast_ is guaranteed not to affect the performance, which depends only on the drivers used, 
i.e. the implementation dealing with the actual processing of the finished data in real time, 
thanks to the eager-execution architecture and caching. 

### Networking tools
_netcast_ comes with a lot of tools generally useful for writing network protocols.
