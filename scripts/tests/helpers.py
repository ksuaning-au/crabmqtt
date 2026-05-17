import struct
import socket
from dataclasses import dataclass

BROKER_HOST = "localhost"
BROKER_PORT = 1883


def encode_remaining_length(length: int) -> bytes:
    encoded = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 128
        encoded.append(byte)
        if length == 0:
            break
    return bytes(encoded)


def decode_remaining_length(data: bytes, start: int = 1) -> tuple[int, int]:
    value = 0
    multiplier = 1
    pos = start
    while True:
        byte = data[pos]
        value += (byte & 127) * multiplier
        multiplier *= 128
        pos += 1
        if (byte & 128) == 0:
            break
    return value, pos - start + 1


@dataclass
class ConnectPacket:
    client_id: str
    protocol_name: bytes = b"MQTT"
    protocol_level: int = 4
    clean_session: bool = True
    keep_alive: int = 60
    username: str | None = None
    password: str | None = None
    will_topic: str | None = None
    will_message: bytes | None = None
    will_qos: int = 0
    will_retain: bool = False


def build_connect_packet(pkt: ConnectPacket) -> bytes:
    connect_flags = 0
    if pkt.clean_session:
        connect_flags |= 0x02
    if pkt.will_topic is not None:
        connect_flags |= 0x04
        connect_flags |= (pkt.will_qos & 0x03) << 3
        if pkt.will_retain:
            connect_flags |= 0x20
    if pkt.password is not None:
        connect_flags |= 0x40
    if pkt.username is not None:
        connect_flags |= 0x80

    variable_header = (
        struct.pack(">H", len(pkt.protocol_name))
        + pkt.protocol_name
        + bytes([pkt.protocol_level, connect_flags])
        + struct.pack(">H", pkt.keep_alive)
    )

    payload = struct.pack(">H", len(pkt.client_id)) + pkt.client_id.encode()

    if pkt.will_topic is not None:
        payload += struct.pack(">H", len(pkt.will_topic)) + pkt.will_topic.encode()
        will_msg = pkt.will_message if pkt.will_message is not None else b""
        payload += struct.pack(">H", len(will_msg)) + will_msg

    if pkt.username is not None:
        payload += struct.pack(">H", len(pkt.username)) + pkt.username.encode()
    if pkt.password is not None:
        payload += struct.pack(">H", len(pkt.password)) + pkt.password.encode()

    remaining = len(variable_header) + len(payload)
    return (
        bytes([0x10]) + encode_remaining_length(remaining) + variable_header + payload
    )


def parse_connack(data: bytes) -> tuple[int, int]:
    assert data[0] == 0x20, f"Not a CONNACK, got type {data[0] >> 4}"
    session_present = data[2] & 0x01
    return_code = data[3]
    return session_present, return_code


def build_subscribe_packet(packet_id: int, topics: list[tuple[str, int]]) -> bytes:
    variable_header = struct.pack(">H", packet_id)
    payload = bytearray()
    for topic, qos in topics:
        payload += struct.pack(">H", len(topic)) + topic.encode() + bytes([qos])
    remaining = len(variable_header) + len(payload)
    return (
        bytes([0x82])
        + encode_remaining_length(remaining)
        + variable_header
        + bytes(payload)
    )


def parse_suback(data: bytes) -> tuple[int, list[int]]:
    assert data[0] == 0x90, f"Not a SUBACK, got type {data[0] >> 4}"
    remaining_len, header_size = decode_remaining_length(data)
    packet_id = struct.unpack(">H", data[header_size : header_size + 2])[0]
    return_codes = list(data[header_size + 2 : header_size + remaining_len])
    return packet_id, return_codes


def build_unsubscribe_packet(packet_id: int, topics: list[str]) -> bytes:
    variable_header = struct.pack(">H", packet_id)
    payload = bytearray()
    for topic in topics:
        payload += struct.pack(">H", len(topic)) + topic.encode()
    remaining = len(variable_header) + len(payload)
    return (
        bytes([0xA2])
        + encode_remaining_length(remaining)
        + variable_header
        + bytes(payload)
    )


def parse_unsuback(data: bytes) -> int:
    assert data[0] == 0xB0, f"Not an UNSUBACK, got type {data[0] >> 4}"
    return struct.unpack(">H", data[2:4])[0]


def build_publish_packet(
    topic: str,
    payload: bytes,
    qos: int = 0,
    packet_id: int | None = None,
    retain: bool = False,
    dup: bool = False,
) -> bytes:
    fixed_header = 0x30
    if retain:
        fixed_header |= 0x01
    fixed_header |= (qos & 0x03) << 1
    if dup:
        fixed_header |= 0x08

    variable_header = struct.pack(">H", len(topic)) + topic.encode()
    if qos > 0:
        assert packet_id is not None, "packet_id required for QoS > 0"
        variable_header += struct.pack(">H", packet_id)

    remaining = len(variable_header) + len(payload)
    return (
        bytes([fixed_header])
        + encode_remaining_length(remaining)
        + variable_header
        + payload
    )


def parse_publish(data: bytes) -> dict:
    assert (data[0] & 0xF0) == 0x30, f"Not a PUBLISH, got type {data[0] >> 4}"
    remaining_len, header_size = decode_remaining_length(data)
    dup = bool(data[0] & 0x08)
    qos = (data[0] & 0x06) >> 1
    retain = bool(data[0] & 0x01)
    pos = header_size
    topic_len = struct.unpack(">H", data[pos : pos + 2])[0]
    pos += 2
    topic = data[pos : pos + topic_len].decode()
    pos += topic_len
    packet_id = None
    if qos > 0:
        packet_id = struct.unpack(">H", data[pos : pos + 2])[0]
        pos += 2
    payload = data[pos : pos + remaining_len - (pos - header_size)]
    return {
        "dup": dup,
        "qos": qos,
        "retain": retain,
        "topic": topic,
        "packet_id": packet_id,
        "payload": payload,
    }


def parse_puback(data: bytes) -> int:
    assert data[0] == 0x40, f"Not a PUBACK, got type {data[0] >> 4}"
    return struct.unpack(">H", data[2:4])[0]


def build_puback(packet_id: int) -> bytes:
    return bytes([0x40, 0x02]) + struct.pack(">H", packet_id)


def parse_pubrec(data: bytes) -> int:
    assert data[0] == 0x50, f"Not a PUBREC, got type {data[0] >> 4}"
    return struct.unpack(">H", data[2:4])[0]


def build_pubrec(packet_id: int) -> bytes:
    return bytes([0x50, 0x02]) + struct.pack(">H", packet_id)


def parse_pubrel(data: bytes) -> int:
    assert data[0] == 0x62, f"Not a PUBREL, got type {data[0] >> 4}"
    return struct.unpack(">H", data[2:4])[0]


def build_pubrel(packet_id: int) -> bytes:
    return bytes([0x62, 0x02]) + struct.pack(">H", packet_id)


def parse_pubcomp(data: bytes) -> int:
    assert data[0] == 0x70, f"Not a PUBCOMP, got type {data[0] >> 4}"
    return struct.unpack(">H", data[2:4])[0]


def build_pubcomp(packet_id: int) -> bytes:
    return bytes([0x70, 0x02]) + struct.pack(">H", packet_id)


def build_pingreq() -> bytes:
    return bytes([0xC0, 0x00])


def parse_pingresp(data: bytes) -> bool:
    return data[0] == 0xD0 and data[1] == 0x00


def build_disconnect() -> bytes:
    return bytes([0xE0, 0x00])


def do_connect(
    sock: socket.socket,
    client_id: str,
    clean_session: bool = True,
    keep_alive: int = 60,
    will_topic: str | None = None,
    will_message: bytes | None = None,
    will_qos: int = 0,
    will_retain: bool = False,
    username: str | None = None,
    password: str | None = None,
) -> int:
    pkt = ConnectPacket(
        client_id=client_id,
        clean_session=clean_session,
        keep_alive=keep_alive,
        will_topic=will_topic,
        will_message=will_message,
        will_qos=will_qos,
        will_retain=will_retain,
        username=username,
        password=password,
    )
    sock.sendall(build_connect_packet(pkt))
    _, rc = parse_connack(sock.recv(4))
    return rc


def do_subscribe(
    sock: socket.socket, packet_id: int, topics: list[tuple[str, int]]
) -> list[int]:
    sock.sendall(build_subscribe_packet(packet_id, topics))
    _, return_codes = parse_suback(sock.recv(1024))
    return return_codes


def recv_puback(sock: socket.socket) -> int:
    data = sock.recv(4)
    return parse_puback(data)


def recv_publish(sock: socket.socket) -> dict:
    chunk = sock.recv(1)
    remaining_len, _ = decode_remaining_length(chunk + sock.recv(4), start=1)
    total_size = remaining_len + 2
    data = chunk + _read_exactly(sock, total_size - 1)
    return parse_publish(data)


def recv_packet(sock: socket.socket, packet_type_nibble: int | None = None) -> bytes:
    chunk = sock.recv(1)
    remaining_len, header_size = decode_remaining_length(chunk + sock.recv(4), start=1)
    total_size = remaining_len + 1 + (header_size - 1)
    data = chunk + _read_exactly(sock, total_size - 1)
    return data


def _read_exactly(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        buf.extend(chunk)
    return bytes(buf)


def unique_id(prefix: str = "test") -> str:
    import os

    return f"{prefix}-{os.urandom(4).hex()}"
