import pytest
import socket
import time

from helpers import (
    do_connect,
    do_subscribe,
    build_publish_packet,
    parse_pubrec,
    parse_pubrel,
    parse_pubcomp,
    build_pubrel,
    build_pubcomp,
    recv_publish,
    build_pubrec,
    unique_id,
)


def test_publish_qos2_expect_pubrec(sock):
    cid = unique_id("q2pub")
    do_connect(sock, cid)
    sock.sendall(build_publish_packet("test/qos2", b"hello", qos=2, packet_id=10))
    packet_id = parse_pubrec(sock.recv(4))
    assert packet_id == 10


def test_publish_qos2_complete_flow(sock):
    cid = unique_id("q2flow")
    do_connect(sock, cid)

    sock.sendall(build_publish_packet("test/qos2", b"hello", qos=2, packet_id=20))
    recv_id = parse_pubrec(sock.recv(4))
    assert recv_id == 20

    sock.sendall(build_pubrel(recv_id))
    comp_id = parse_pubcomp(sock.recv(4))
    assert comp_id == 20


def test_publish_qos2_multiple_messages(sock):
    cid = unique_id("q2multi")
    do_connect(sock, cid)

    for pid in [1, 2, 3]:
        sock.sendall(build_publish_packet("test/qos2", b"m", qos=2, packet_id=pid))
        recv_id = parse_pubrec(sock.recv(4))
        assert recv_id == pid
        sock.sendall(build_pubrel(recv_id))
        comp_id = parse_pubcomp(sock.recv(4))
        assert comp_id == pid


def test_publish_qos2_forwarded_to_subscriber(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/qos2fwd/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [(topic, 2)])
    time.sleep(0.2)

    pub_sock.sendall(build_publish_packet(topic, b"qos2-data", qos=2, packet_id=30))
    recv_id = parse_pubrec(pub_sock.recv(4))
    assert recv_id == 30

    pub_sock.sendall(build_pubrel(recv_id))
    comp_id = parse_pubcomp(pub_sock.recv(4))
    assert comp_id == 30

    msg = recv_publish(sub_sock)
    assert msg["topic"] == topic
    assert msg["payload"] == b"qos2-data"
    assert msg["qos"] == 2


def test_publish_qos2_wrong_pubrel_rejected(sock):
    cid = unique_id("q2bad")
    do_connect(sock, cid)

    sock.sendall(build_publish_packet("test/qos2", b"data", qos=2, packet_id=40))
    recv_id = parse_pubrec(sock.recv(4))
    assert recv_id == 40

    sock.sendall(build_pubrel(9999))
    with pytest.raises(socket.timeout):
        sock.recv(2)


def test_publish_qos2_qos1_subscriber_granted_qos1(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/qos2downgrade/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    return_codes = do_subscribe(sub_sock, 1, [(topic, 1)])
    assert return_codes == [1]

    pub_sock.sendall(build_publish_packet(topic, b"data", qos=2, packet_id=50))
    recv_id = parse_pubrec(pub_sock.recv(4))
    assert recv_id == 50
    pub_sock.sendall(build_pubrel(recv_id))
    comp_id = parse_pubcomp(pub_sock.recv(4))
    assert comp_id == 50

    msg = recv_publish(sub_sock)
    assert msg["qos"] == 1
