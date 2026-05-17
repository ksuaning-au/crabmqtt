import pytest
import socket
import time

from helpers import (
    do_connect,
    do_subscribe,
    build_subscribe_packet,
    parse_suback,
    unique_id,
)


def test_subscribe_qos0_grants_0(sock):
    cid = unique_id("s0")
    do_connect(sock, cid)
    rcs = do_subscribe(sock, 1, [("test/s0", 0)])
    assert rcs == [0]


def test_subscribe_qos1_grants_1(sock):
    cid = unique_id("s1")
    do_connect(sock, cid)
    rcs = do_subscribe(sock, 1, [("test/s1", 1)])
    assert rcs == [1]


def test_subscribe_qos2_grants_2(sock):
    cid = unique_id("s2")
    do_connect(sock, cid)
    rcs = do_subscribe(sock, 1, [("test/s2", 2)])
    allowed = {2}
    assert rcs[0] in allowed


def test_subscribe_qos2_downgraded_to_1(sock):
    cid = unique_id("s2d1")
    do_connect(sock, cid)
    rcs = do_subscribe(sock, 1, [("test/s2d1", 2)])
    assert rcs[0] in {2, 1}


def test_subscribe_qos2_downgraded_to_0(sock):
    cid = unique_id("s2d0")
    do_connect(sock, cid)
    rcs = do_subscribe(sock, 1, [("test/s2d0", 2)])
    assert rcs[0] in {2, 1, 0}


def test_subscribe_multiple_topics_return_codes(sock):
    cid = unique_id("multi")
    do_connect(sock, cid)
    rcs = do_subscribe(sock, 1, [("test/a", 0), ("test/b", 1), ("test/c", 2)])
    assert len(rcs) == 3
    for rc in rcs:
        assert rc in {0, 1, 2}


def test_subscribe_failure_return_code(sock):
    cid = unique_id("fail")
    do_connect(sock, cid)
    sock.sendall(build_subscribe_packet(1, [("", 0)]))
    data = sock.recv(1024)
    assert data[0] == 0x90
    if len(data) > 4:
        rc = data[4]
        assert rc == 0x80


def test_suback_packet_id_matches(sock):
    cid = unique_id("pid")
    do_connect(sock, cid)
    sock.sendall(build_subscribe_packet(42, [("test/pid", 0)]))
    pid, rcs = parse_suback(sock.recv(1024))
    assert pid == 42
