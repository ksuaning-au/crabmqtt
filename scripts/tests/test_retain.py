import pytest
import socket
import time
import struct

from helpers import (
    do_connect,
    do_subscribe,
    build_publish_packet,
    build_subscribe_packet,
    encode_remaining_length,
    recv_publish,
    recv_packet,
    parse_suback,
    unique_id,
    recv_puback,
)


def test_publish_retain_stored(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/retain/{unique_id('t')}"

    pub_cid = unique_id("pub")
    do_connect(pub_sock, pub_cid)
    pub_sock.sendall(build_publish_packet(topic, b"stored", qos=0, retain=True))
    time.sleep(0.3)

    sub_cid = unique_id("sub")
    do_connect(sub_sock, sub_cid)
    sub_sock.sendall(build_subscribe_packet(1, [(topic, 0)]))
    data = recv_packet(sub_sock)

    if data[0] == 0x90:
        data = recv_packet(sub_sock)

    assert (data[0] & 0xF0) == 0x30, f"Expected PUBLISH, got type {data[0] >> 4}"
    msg = _parse_publish_bytes(data)
    assert msg["topic"] == topic
    assert msg["payload"] == b"stored"
    assert msg["retain"] is True


def test_publish_retain_overwrite(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/retover/{unique_id('t')}"

    pub_cid = unique_id("pub")
    do_connect(pub_sock, pub_cid)
    pub_sock.sendall(build_publish_packet(topic, b"first", qos=0, retain=True))
    pub_sock.sendall(build_publish_packet(topic, b"second", qos=0, retain=True))
    time.sleep(0.3)

    sub_cid = unique_id("sub")
    do_connect(sub_sock, sub_cid)
    sub_sock.sendall(build_subscribe_packet(1, [(topic, 0)]))
    data = recv_packet(sub_sock)
    if data[0] == 0x90:
        data = recv_packet(sub_sock)

    msg = _parse_publish_bytes(data)
    assert msg["payload"] == b"second"


def test_publish_retain_delete_with_empty_payload(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/retdel/{unique_id('t')}"

    pub_cid = unique_id("pub")
    do_connect(pub_sock, pub_cid)
    pub_sock.sendall(build_publish_packet(topic, b"to-delete", qos=0, retain=True))
    time.sleep(0.1)

    pub_sock.sendall(build_publish_packet(topic, b"", qos=0, retain=True))
    time.sleep(0.3)

    sub_cid = unique_id("sub")
    do_connect(sub_sock, sub_cid)
    sub_sock.sendall(build_subscribe_packet(1, [(topic, 0)]))
    data = sub_sock.recv(1024)
    assert data[0] == 0x90, "Expected SUBACK"
    with pytest.raises(socket.timeout):
        sub_sock.recv(1)


def test_publish_retain_qos_preserved(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/retqos/{unique_id('t')}"

    pub_cid = unique_id("pub")
    do_connect(pub_sock, pub_cid)
    pub_sock.sendall(
        build_publish_packet(topic, b"qos1-retained", qos=1, packet_id=1, retain=True)
    )
    recv_puback(pub_sock)
    time.sleep(0.2)

    sub_cid = unique_id("sub")
    do_connect(sub_sock, sub_cid)
    sub_sock.sendall(build_subscribe_packet(1, [(topic, 0)]))
    data = recv_packet(sub_sock)
    if data[0] == 0x90:
        data = recv_packet(sub_sock)

    qos = (data[0] & 0x06) >> 1
    assert qos == 1


def test_retain_not_sent_to_existing_subscribers(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/retnew/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)
    do_subscribe(sub_sock, 1, [(topic, 0)])

    pub_sock.sendall(build_publish_packet(topic, b"retained", qos=0, retain=True))
    time.sleep(0.3)

    with pytest.raises(socket.timeout):
        sub_sock.recv(1)


def _parse_publish_bytes(data: bytes) -> dict:
    remaining_len, hdr_size = _decode_len(data)
    pos = hdr_size
    topic_len = (data[pos] << 8) | data[pos + 1]
    pos += 2
    topic = data[pos : pos + topic_len].decode()
    pos += topic_len
    qos = (data[0] & 0x06) >> 1
    if qos > 0:
        pos += 2
    payload = data[pos : pos + remaining_len - (pos - hdr_size)]
    return {
        "topic": topic,
        "payload": payload,
        "qos": qos,
        "retain": bool(data[0] & 0x01),
    }


def _decode_len(data: bytes) -> tuple[int, int]:
    value = 0
    mult = 1
    pos = 1
    while pos < len(data):
        byte = data[pos]
        value += (byte & 127) * mult
        mult *= 128
        pos += 1
        if (byte & 128) == 0:
            break
    return value, pos
