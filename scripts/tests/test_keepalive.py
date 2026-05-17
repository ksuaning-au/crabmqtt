import pytest
import socket
import time

from helpers import (
    do_connect,
    build_pingreq,
    parse_pingresp,
    unique_id,
    build_publish_packet,
)


def test_keep_alive_disconnects_on_timeout(sock):
    cid = unique_id("katime")
    do_connect(sock, cid, keep_alive=2)
    time.sleep(4)
    sock.sendall(build_pingreq())
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(2)


def test_keep_alive_ping_resets_timer(sock):
    cid = unique_id("kaping")
    do_connect(sock, cid, keep_alive=3)
    for _ in range(6):
        time.sleep(2)
        sock.sendall(build_pingreq())
        data = sock.recv(2)
        assert parse_pingresp(data)


def test_keep_alive_publish_resets_timer(sock):
    cid = unique_id("kapub")
    do_connect(sock, cid, keep_alive=2)
    time.sleep(1.5)
    sock.sendall(build_publish_packet("test/keep", b"ping", qos=0))
    time.sleep(1.5)
    sock.sendall(build_pingreq())
    data = sock.recv(2)
    assert parse_pingresp(data)


def test_keep_alive_zero_disables_timeout(sock):
    cid = unique_id("ka0")
    do_connect(sock, cid, keep_alive=0)
    time.sleep(4)
    sock.sendall(build_pingreq())
    data = sock.recv(2)
    assert parse_pingresp(data)


def test_keep_alive_subscribe_resets_timer(sock):
    cid = unique_id("kasub")
    do_connect(sock, cid, keep_alive=2)
    from helpers import build_subscribe_packet, parse_suback

    time.sleep(1.5)
    sock.sendall(build_subscribe_packet(1, [("test/ka", 0)]))
    data = sock.recv(1024)
    assert data[0] == 0x90
    time.sleep(1.5)
    sock.sendall(build_pingreq())
    data = sock.recv(2)
    assert parse_pingresp(data)


def test_keep_alive_half_time_no_disconnect(sock):
    cid = unique_id("kahalf")
    do_connect(sock, cid, keep_alive=4)
    time.sleep(2.5)
    sock.sendall(build_pingreq())
    data = sock.recv(2)
    assert parse_pingresp(data)
