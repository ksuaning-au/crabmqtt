import socket
import pytest

BROKER_HOST = "localhost"
BROKER_PORT = 1883


@pytest.fixture
def sock():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((BROKER_HOST, BROKER_PORT))
    yield s
    s.close()


@pytest.fixture
def two_socks():
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.settimeout(5)
    s1.connect((BROKER_HOST, BROKER_PORT))
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(5)
    s2.connect((BROKER_HOST, BROKER_PORT))
    yield s1, s2
    s1.close()
    s2.close()
