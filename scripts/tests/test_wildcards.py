import pytest
import socket
import time

from helpers import (
    do_connect,
    do_subscribe,
    build_publish_packet,
    recv_publish,
    unique_id,
)


def test_plus_single_level(two_socks):
    pub_sock, sub_sock = two_socks
    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [("sensor/+/temp", 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet("sensor/1/temp", b"val", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["topic"] == "sensor/1/temp"
    assert msg["payload"] == b"val"


def test_plus_matches_any_single_level(two_socks):
    pub_sock, sub_sock = two_socks
    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [("+/status", 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet("lights/status", b"on", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["payload"] == b"on"

    pub_sock.sendall(build_publish_packet("doors/status", b"closed", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["payload"] == b"closed"


def test_plus_does_not_match_multiple_levels(two_socks):
    pub_sock, sub_sock = two_socks
    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [("sensor/+/temp", 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet("sensor/1/floor/temp", b"val", qos=0))
    with pytest.raises(socket.timeout):
        recv_publish(sub_sock)


def test_hash_multilevel(two_socks):
    pub_sock, sub_sock = two_socks
    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [("sensor/#", 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet("sensor/temp", b"t1", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["topic"] == "sensor/temp"

    pub_sock.sendall(build_publish_packet("sensor/1/humidity", b"h1", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["topic"] == "sensor/1/humidity"


def test_hash_match_all(two_socks):
    pub_sock, sub_sock = two_socks
    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [("#", 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet("any/topic/here", b"a", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["payload"] == b"a"

    pub_sock.sendall(build_publish_packet("alone", b"b", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["payload"] == b"b"


def test_hash_does_not_match_system_topics(two_socks):
    pub_sock, sub_sock = two_socks
    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [("#", 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet("$SYS/broker/uptime", b"100", qos=0))
    with pytest.raises(socket.timeout):
        recv_publish(sub_sock)


def test_plus_and_hash_combined(two_socks):
    pub_sock, sub_sock = two_socks
    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [("+/monitor/#", 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet("room1/monitor/temp", b"v1", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["payload"] == b"v1"

    pub_sock.sendall(build_publish_packet("room1/monitor/floor/humidity", b"v2", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["payload"] == b"v2"

    pub_sock.sendall(build_publish_packet("room1/other/val", b"v3", qos=0))
    with pytest.raises(socket.timeout):
        recv_publish(sub_sock)


def test_multiple_subscribers_wildcard(two_socks):
    s1, s2 = two_socks
    topic = unique_id("multi")
    do_connect(s1, unique_id("pub"))
    do_connect(s2, unique_id("sub"))

    do_subscribe(s2, 1, [(f"+/status", 0)])
    time.sleep(0.2)

    s1.sendall(build_publish_packet(f"device1/status", b"ok", qos=0))
    msg = recv_publish(s2)
    assert msg["payload"] == b"ok"
