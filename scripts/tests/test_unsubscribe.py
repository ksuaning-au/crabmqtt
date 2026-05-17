import pytest
import socket
import time

from helpers import (
    do_connect,
    do_subscribe,
    build_unsubscribe_packet,
    parse_unsuback,
    build_publish_packet,
    recv_publish,
    encode_remaining_length,
    unique_id,
    recv_packet,
)


def test_unsubscribe_one_topic(sock):
    cid = unique_id("unsub1")
    do_connect(sock, cid)
    do_subscribe(sock, 1, [("test/unsub", 0)])

    sock.sendall(build_unsubscribe_packet(99, ["test/unsub"]))
    pid = parse_unsuback(sock.recv(4))
    assert pid == 99


def test_unsubscribe_multiple_topics(sock):
    cid = unique_id("unsubm")
    do_connect(sock, cid)
    do_subscribe(sock, 1, [("a", 0), ("b", 0), ("c", 0)])

    sock.sendall(build_unsubscribe_packet(42, ["a", "c"]))
    pid = parse_unsuback(sock.recv(4))
    assert pid == 42


def test_unsubscribe_stops_delivery(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/unsubstop/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [(topic, 0)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet(topic, b"before", qos=0))
    msg = recv_publish(sub_sock)
    assert msg["payload"] == b"before"

    sub_sock.sendall(build_unsubscribe_packet(2, [topic]))
    pid = parse_unsuback(sub_sock.recv(4))
    assert pid == 2

    time.sleep(0.2)
    pub_sock.sendall(build_publish_packet(topic, b"after", qos=0))
    with pytest.raises(socket.timeout):
        recv_publish(sub_sock)


def test_unsubscribe_nonexistent_topic(sock):
    cid = unique_id("unsubne")
    do_connect(sock, cid)
    sock.sendall(build_unsubscribe_packet(7, ["never/subscribed"]))
    pid = parse_unsuback(sock.recv(4))
    assert pid == 7


def test_unsubscribe_wildcard(sock):
    cid = unique_id("unsubwc")
    do_connect(sock, cid)
    do_subscribe(sock, 1, [("sensor/+/temp", 0)])
    sock.sendall(build_unsubscribe_packet(5, ["sensor/+/temp"]))
    pid = parse_unsuback(sock.recv(4))
    assert pid == 5


def test_unsubscribe_then_resubscribe(sock):
    cid = unique_id("unsubres")
    do_connect(sock, cid)
    do_subscribe(sock, 1, [("test/resub", 0)])
    sock.sendall(build_unsubscribe_packet(2, ["test/resub"]))
    pid = parse_unsuback(sock.recv(4))
    assert pid == 2

    rcs = do_subscribe(sock, 3, [("test/resub", 0)])
    assert rcs == [0]
