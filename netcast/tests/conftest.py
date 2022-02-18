import pytest

from netcast.tools.arrangements import ArrangementT
from netcast.tools.arrangements import (
    ClassArrangement,
    ClassFileIOArrangement,
    Arrangement,
    FileIOArrangement,
    ClassSSLSocketArrangement,
    SSLSocketArrangement,
)

class_arrangements = {ClassArrangement, *ClassArrangement.__subclasses__()}
class_arrangements.discard(Arrangement)
class_arrangements.discard(ClassFileIOArrangement)
class_arrangements.discard(ClassSSLSocketArrangement)


@pytest.fixture(params=class_arrangements, scope="session")
def inj_class_arrangement(request) -> ArrangementT:
    return request.param


arrangements = {Arrangement, *Arrangement.__subclasses__()}
arrangements.discard(FileIOArrangement)
arrangements.discard(SSLSocketArrangement)


@pytest.fixture(params=arrangements, scope="session")
def inj_arrangement(request) -> ArrangementT:
    return request.param
