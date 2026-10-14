import pytest
import requests

from signal_scout.store import SeenStore


@pytest.fixture
def session():
    return requests.Session()


@pytest.fixture
def store():
    s = SeenStore(":memory:")
    yield s
    s.close()
