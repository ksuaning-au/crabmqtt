import pytest
import socket
import time

from helpers import (
    do_connect,
    do_subscribe,
    build_disconnect,
    build_publish_packet,
    recv_publish,
    unique_id,
    build_pingreq,
)


def test_disconnect_clean_close(sock):
    cid = unique_id("disc")
    do_connect(sock, cid)
    sock.sendall(build_disconnect())
    time.sleep(0.3)
    sock.sendall(build_pingreq())
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(2)


def test_disconnect_removes_subscriber(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/discsub/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(sub_sock, sub_cid)

    do_subscribe(sub_sock, 1, [(topic, 0)])
    time.sleep(0.2)

    sub_sock.sendall(build_disconnect())
    sub_sock.close()
    time.sleep(0.3)

    pub_sock.sendall(build_publish_packet(topic, b"after", qos=0))
    with pytest.raises(socket.timeout):
        pub_sock.recv(1)


def test_disconnect_no_will_sent(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/nowill/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(
        sub_sock,
        sub_cid,
        will_topic=topic,
        will_message=b"should-not-appear",
    )
    do_subscribe(pub_sock, 1, [(topic, 0)])

    sub_sock.sendall(build_disconnect())
    sub_sock.close()
    time.sleep(0.3)

    with pytest.raises(socket.timeout):
        recv_publish(pub_sock)


def test_abrupt_disconnect_sends_will(two_socks):
    pub_sock, sub_sock = two_socks
    topic = f"test/will/{unique_id('t')}"

    pub_cid = unique_id("pub")
    sub_cid = unique_id("sub")
    do_connect(pub_sock, pub_cid)
    do_connect(
        sub_sock,
        sub_cid,
        will_topic=topic,
        will_message=b"unexpected-bye",
    )
    do_subscribe(pub_sock, 1, [(topic, 0)])
    time.sleep(0.2)

    sub_sock.close()
    time.sleep(0.5)

    msg = recv_publish(pub_sock)
    assert msg["topic"] == topic
    assert msg["payload"] == b"unexpected-bye"


def test_disconnect_multiple_times_no_error(sock):
    cid = unique_id("discm")
    do_connect(sock, cid)
    sock.sendall(build_disconnect())
    time.sleep(0.2)
    with pytest.raises((socket.timeout, OSError)):
        sock.recv(1)


def test_disconnect_cleans_client_from_state(sock):
    cid = unique_id("discstate")
    do_connect(sock, cid)
    sock.sendall(build_disconnect())
    time.sleep(0.3)

    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(5)
    s2.connect(("localhost", 1883))
    rc = do_connect(s2, cid)
    assert rc == 0x00
    s2.close()
