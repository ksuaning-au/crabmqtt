import pytest
import socket
import time

from helpers import (
    do_connect,
    do_subscribe,
    build_publish_packet,
    parse_puback,
    recv_publish,
    encode_remaining_length,
    unique_id,
    build_disconnect,
)


def test_publish_qos0_no_ack(sock):
    cid = unique_id("pubq0")
    do_connect(sock, cid)
    sock.sendall(build_publish_packet("test/qos0", b"hello", qos=0))
    with pytest.raises(socket.timeout):
        sock.recv(1)


def test_publish_qos1_expect_puback(sock):
    cid = unique_id("pubq1")
    do_connect(sock, cid)
    sock.sendall(build_publish_packet("test/qos1", b"hello", qos=1, packet_id=1))
    packet_id = parse_puback(sock.recv(4))
    assert packet_id == 1


def test_publish_qos1_multiple_ids(sock):
    cid = unique_id("pubq1m")
    do_connect(sock, cid)
    for pid in [1, 2, 3, 65535]:
        sock.sendall(build_publish_packet("test/qos1", b"data", qos=1, packet_id=pid))
        ack_id = parse_puback(sock.recv(4))
        assert ack_id == pid


def test_publish_qos1_forwarded_to_subscriber(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/qos1fwd/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [(topic, 1)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet(topic, b"forwarded", qos=1, packet_id=42))
    ack_id = parse_puback(pub_sock.recv(4))
    assert ack_id == 42

    msg = recv_publish(sub_sock)
    assert msg["topic"] == topic
    assert msg["payload"] == b"forwarded"
    assert msg["qos"] == 1


def test_publish_qos1_dup_flag_not_set_initially(sock):
    cid = unique_id("dupcheck")
    do_connect(sock, cid)
    raw = build_publish_packet("test/dup", b"data", qos=1, packet_id=1, dup=False)
    assert (raw[0] & 0x08) == 0


def test_publish_qos1_payload_binary(sock):
    cid = unique_id("binary")
    do_connect(sock, cid)
    binary = bytes(range(256))
    sock.sendall(build_publish_packet("test/bin", binary, qos=1, packet_id=1))
    ack_id = parse_puback(sock.recv(4))
    assert ack_id == 1


def test_publish_qos0_large_payload(sock):
    cid = unique_id("large")
    do_connect(sock, cid)
    payload = b"x" * 4096
    sock.sendall(build_publish_packet("test/large", payload, qos=0))
    with pytest.raises(socket.timeout):
        sock.recv(1)


def test_publish_qos1_no_subscriber_no_crash(sock):
    cid = unique_id("noscrash")
    do_connect(sock, cid)
    sock.sendall(build_publish_packet("test/nosub", b"data", qos=1, packet_id=1))
    ack_id = parse_puback(sock.recv(4))
    assert ack_id == 1
