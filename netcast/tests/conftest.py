import pytest

from netcast.arrangement import AT, CAT
from netcast.arrangement import (
    ClassArrangement, ClassFileIOArrangement,
    Arrangement, FileIOArrangement,
    ClassSSLSocketArrangement, SSLSocketArrangement
)

class_arrangements = {ClassArrangement, *ClassArrangement.__subclasses__()}
class_arrangements.discard(Arrangement)
class_arrangements.discard(ClassFileIOArrangement)
class_arrangements.discard(ClassSSLSocketArrangement)


@pytest.fixture(params=class_arrangements, scope='session')
def ca(request) -> CAT:
    yield request.param


arrangements = {Arrangement, *Arrangement.__subclasses__()}
arrangements.discard(FileIOArrangement)
arrangements.discard(SSLSocketArrangement)


@pytest.fixture(params=arrangements, scope='session')
def a(request) -> AT:
    yield request.param


def pytest_configure(config):
    config.inicfg['asyncio_mode'] = 'auto'
