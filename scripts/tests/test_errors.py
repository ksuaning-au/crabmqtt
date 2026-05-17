import pytest
import socket
import time
import struct

from helpers import (
    do_connect,
    do_subscribe,
    build_connect_packet,
    ConnectPacket,
    build_publish_packet,
    build_subscribe_packet,
    build_pingreq,
    build_disconnect,
    encode_remaining_length,
    decode_remaining_length,
    unique_id,
)


def test_connect_twice_disconnects_first(sock):
    cid = unique_id("dup")
    do_connect(sock, cid)

    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(5)
    s2.connect(("localhost", 1883))
    rc = do_connect(s2, cid)
    assert rc == 0x00
    time.sleep(0.3)

    sock.sendall(build_pingreq())
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(2)
    s2.close()


def test_subscribe_before_connect_closes(sock):
    sock.sendall(build_subscribe_packet(1, [("test/no", 0)]))
    time.sleep(0.3)
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(1)


def test_publish_before_connect_closes(sock):
    sock.sendall(build_publish_packet("test/no", b"data", qos=0))
    time.sleep(0.3)
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(1)


def test_pingreq_before_connect(sock):
    sock.sendall(build_pingreq())
    time.sleep(0.3)
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(1)


def test_malformed_remaining_length_terminates(sock):
    do_connect(sock, unique_id("mal"))
    remaining = bytes([0x80, 0x80, 0x80, 0x80, 0x80])
    sock.sendall(bytes([0x30]) + remaining)
    time.sleep(0.3)
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(1)


def test_invalid_packet_type_zero(sock):
    do_connect(sock, unique_id("inv0"))
    sock.sendall(bytes([0x00, 0x00]))
    time.sleep(0.3)
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(1)


def test_packet_truncated_mid_publish(sock):
    cid = unique_id("trunc")
    do_connect(sock, cid)
    sock.sendall(
        bytes(
            [0x30, 0x10, 0x00, 0x05, ord("t"), ord("o"), ord("p"), ord("i"), ord("c")]
        )
    )
    time.sleep(0.3)
    sock.sendall(build_pingreq())
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(2)


def test_invalid_qos_3(sock):
    cid = unique_id("qos3")
    do_connect(sock, cid)
    raw = bytearray(build_publish_packet("test/qos3", b"data", qos=0))
    raw[0] |= 0x06
    sock.sendall(bytes(raw))
    time.sleep(0.3)
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(1)


def test_subscribe_invalid_qos(sock):
    cid = unique_id("subiq")
    do_connect(sock, cid)
    topics_with_qos = struct.pack(">H", 4) + b"test" + bytes([3])
    sub_raw = bytes([0x82]) + encode_remaining_length(2 + len(topics_with_qos))
    sub_raw += struct.pack(">H", 1) + topics_with_qos
    sock.sendall(sub_raw)
    resp = sock.recv(1024)
    assert resp[0] == 0x90


def test_connect_reserved_flag_set(sock):
    pkt = ConnectPacket(client_id=unique_id("resflag"))
    raw = bytearray(build_connect_packet(pkt))
    raw[0] |= 0x0E
    sock.sendall(bytes(raw))
    with pytest.raises(socket.timeout):
        sock.recv(1)
