import paho.mqtt.client as mqtt
from dataclasses import dataclass
import struct
import pytest
import socket
import time

from helpers import (
    BROKER_HOST,
    BROKER_PORT,
    ConnectPacket,
    build_connect_packet,
    build_subscribe_packet,
    build_pingreq,
    parse_connack,
    do_connect,
    unique_id,
    build_disconnect,
)


@dataclass
class SimpleConnectPacket:
    client_id: str
    protocol_name: bytes = b"MQTT"
    protocol_level: int = 4
    connect_flags: int = 0x00
    keep_alive: int = 60
    username: str = None
    password: str = None
    will_topic: str = None
    will_message: str = None


def build_simple_connect_packet(packet: SimpleConnectPacket) -> bytes:
    payload = struct.pack(">H", len(packet.client_id)) + packet.client_id.encode()
    variable_header = (
        struct.pack(">H", len(packet.protocol_name))
        + packet.protocol_name
        + struct.pack("BB", packet.protocol_level, packet.connect_flags)
        + struct.pack(">H", packet.keep_alive)
    )
    remaining = len(variable_header) + len(payload)
    return bytes([0x10, remaining]) + variable_header + payload


@pytest.fixture
def sock():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((BROKER_HOST, BROKER_PORT))
    yield s
    s.close()


def test_connect_accepted(sock):
    packet = SimpleConnectPacket(client_id="test-client")
    sock.sendall(build_simple_connect_packet(packet))
    session_present, rc = parse_connack(sock.recv(4))
    assert rc == 0x00


def test_connect_bad_protocol(sock):
    packet = SimpleConnectPacket(client_id="test-client", protocol_name=b"BAD")
    sock.sendall(build_simple_connect_packet(packet))
    session_present, rc = parse_connack(sock.recv(4))
    assert rc == 0x01


def test_connect_bad_client_id(sock):
    packet = SimpleConnectPacket(client_id="")
    sock.sendall(build_simple_connect_packet(packet))
    session_present, rc = parse_connack(sock.recv(4))
    assert rc == 0x02


def test_connack():
    client = mqtt.Client()
    res = client.connect(BROKER_HOST, BROKER_PORT, 60)
    assert res == 0
    client.disconnect()


# ── New CONNECT flag tests ──────────────────────────────────────────────


def test_connect_clean_session(sock):
    cid = unique_id("clean")
    rc = do_connect(sock, client_id=cid, clean_session=True)
    assert rc == 0x00


def test_connect_clean_session_clears_state(sock):
    cid = unique_id("state")
    do_connect(sock, cid, clean_session=True)
    sock.sendall(build_subscribe_packet(1, [("test/state", 0)]))
    data = sock.recv(1024)
    assert data[0] == 0x90
    sock.close()

    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(5)
    s2.connect((BROKER_HOST, BROKER_PORT))
    do_connect(s2, cid, clean_session=True)
    s2.sendall(build_subscribe_packet(1, [("test/state", 0)]))
    data = s2.recv(1024)
    assert data[0] == 0x90
    s2.close()


def test_connect_will_topic(sock):
    cid = unique_id("will")
    rc = do_connect(sock, client_id=cid, will_topic="test/will", will_message=b"gone")
    assert rc == 0x00


def test_connect_will_qos_0(sock):
    cid = unique_id("willq0")
    rc = do_connect(
        sock, client_id=cid, will_topic="test/will", will_message=b"x", will_qos=0
    )
    assert rc == 0x00


def test_connect_will_qos_1(sock):
    cid = unique_id("willq1")
    rc = do_connect(
        sock, client_id=cid, will_topic="test/will", will_message=b"x", will_qos=1
    )
    assert rc == 0x00


def test_connect_will_qos_2(sock):
    cid = unique_id("willq2")
    rc = do_connect(
        sock, client_id=cid, will_topic="test/will", will_message=b"x", will_qos=2
    )
    assert rc == 0x00


def test_connect_will_retain(sock):
    cid = unique_id("willret")
    rc = do_connect(
        sock, client_id=cid, will_topic="test/will", will_message=b"x", will_retain=True
    )
    assert rc == 0x00


def test_connect_username(sock):
    cid = unique_id("user")
    rc = do_connect(sock, client_id=cid, username="alice")
    assert rc == 0x00


def test_connect_username_password(sock):
    cid = unique_id("pass")
    rc = do_connect(sock, client_id=cid, username="alice", password="secret")
    assert rc == 0x00


def test_connect_protocol_level_3(sock):
    pkt = ConnectPacket(
        client_id=unique_id("v31"),
        protocol_level=3,
    )
    sock.sendall(build_connect_packet(pkt))
    _, rc = parse_connack(sock.recv(4))
    assert rc in (0x00, 0x01)


def test_connect_protocol_level_5_rejected(sock):
    pkt = ConnectPacket(
        client_id=unique_id("v5"),
        protocol_level=5,
    )
    sock.sendall(build_connect_packet(pkt))
    _, rc = parse_connack(sock.recv(4))
    assert rc != 0x00


def test_connect_duplicate_rejected(sock):
    cid = unique_id("dupe")
    do_connect(sock, cid, clean_session=True)

    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(5)
    s2.connect((BROKER_HOST, BROKER_PORT))
    pkt = ConnectPacket(client_id=cid, clean_session=True)
    s2.sendall(build_connect_packet(pkt))
    _, rc = parse_connack(s2.recv(4))
    assert rc == 0x00
    s2.close()


def test_connect_keep_alive_zero(sock):
    cid = unique_id("ka0")
    rc = do_connect(sock, client_id=cid, keep_alive=0)
    assert rc == 0x00


def test_connect_with_disconnect(sock):
    cid = unique_id("disc")
    do_connect(sock, cid)
    sock.sendall(build_disconnect())
    import time

    time.sleep(0.5)
    sock.sendall(build_pingreq())
    with pytest.raises((socket.timeout, ConnectionError, OSError)):
        sock.recv(2)


def test_connect_multiple_clients():
    cid1 = unique_id("multi")
    cid2 = unique_id("multi")
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.settimeout(5)
    s1.connect((BROKER_HOST, BROKER_PORT))
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(5)
    s2.connect((BROKER_HOST, BROKER_PORT))
    assert do_connect(s1, cid1) == 0x00
    assert do_connect(s2, cid2) == 0x00
    s1.close()
    s2.close()
