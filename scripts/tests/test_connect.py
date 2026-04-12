import paho.mqtt.client as mqtt
from dataclasses import dataclass
import struct
import pytest
import socket

BROKER_HOST = "localhost"
BROKER_PORT = 1883

@dataclass
class ConnectPacket:
    client_id: str
    protocol_name: bytes = b'MQTT'
    protocol_level: int = 4
    connect_flags: int = 0x00    
    keep_alive: int = 60
    username: str = None
    password: str  = None
    will_topic: str = None
    will_message: str = None


def build_connect_packet(packet: ConnectPacket) -> bytes:
    payload = struct.pack(">H", len(packet.client_id)) + packet.client_id.encode()
    variable_header = (
        struct.pack(">H", len(packet.protocol_name)) + packet.protocol_name +
        struct.pack("BB", packet.protocol_level, packet.connect_flags) +
        struct.pack(">H", packet.keep_alive)
    )
    remaining = len(variable_header) + len(payload)
    return bytes([0x10, remaining]) + variable_header + payload


def parse_connack(data: bytes) -> tuple[int, int]:
    assert data[0] == 0x20, "Not a CONNACK packet"
    assert data[1] == 0x02, "CONNACK remaining length must be 2"
    session_present = (data[2] & 0x01)
    return_code = data[3]
    return session_present, return_code

# Raw socket or use Paho? Paho easier, raw socket can test more edge cases...
@pytest.fixture
def sock():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((BROKER_HOST, BROKER_PORT))
    yield s
    s.close()


def test_connect_accepted(sock):
    packet = ConnectPacket(client_id="test-client")
    sock.sendall(build_connect_packet(packet))
    session_present, rc = parse_connack(sock.recv(4))
    assert rc == 0x00

# We expect this to fail as currently not implemented..
def test_connect_bad_protocol(sock):
    packet = ConnectPacket(client_id="test-client", protocol_name=b'BAD')
    sock.sendall(build_connect_packet(packet))
    session_present, rc = parse_connack(sock.recv(4))
    assert rc == 0x01

# Also expected to fail atm...
def test_connect_bad_client_id(sock):
    packet = ConnectPacket(client_id="")
    sock.sendall(build_connect_packet(packet))
    session_present, rc = parse_connack(sock.recv(4))
    assert rc == 0x02

def test_connack():
    client = mqtt.Client()
    res = client.connect(BROKER_HOST, BROKER_PORT, 60)
    assert res == 0
    client.disconnect()