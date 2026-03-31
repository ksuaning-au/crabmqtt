#!/usr/bin/env python3
import time
import threading
import paho.mqtt.client as mqtt

# Configuration
BROKER = "127.0.0.1"
PORT = 1883
TOPIC = "benchmark/test"

NUM_PUBLISHERS = 10  # How many concurrent publishers
NUM_SUBSCRIBERS = 5  # How many concurrent subscribers
MESSAGES_PER_PUBLISHER = 1000  # How many messages each publisher sends

total_published = 0
total_received = 0
failures = 0

start_time = 0
end_time = 0

lock = threading.Lock()


def on_connect_sub(client, userdata, flags, rc):
    # rc 0 means successful connection
    if rc == 0:
        client.subscribe(TOPIC, qos=0)
    else:
        print(f"Subscriber connection failed with code {rc}")


def on_message_sub(client, userdata, msg):
    global total_received
    with lock:
        total_received += 1


def subscriber_task(client_id):
    # Depending on paho-mqtt version, CallbackAPIVersion might be needed,
    # but for broad compatibility we stick to standard instantiation.
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect_sub
    client.on_message = on_message_sub

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except Exception as e:
        global failures
        with lock:
            failures += 1
        print(f"Sub {client_id} failed to connect: {e}")


def publisher_task(client_id):
    client = mqtt.Client(client_id=client_id)

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except Exception as e:
        global failures
        with lock:
            failures += 1
        print(f"Pub {client_id} failed to connect: {e}")
        return

    global total_published
    for i in range(MESSAGES_PER_PUBLISHER):
        payload = f"{client_id}-msg-{i}"

        try:
            info = client.publish(TOPIC, payload, qos=0)
            info.wait_for_publish()  # Block until message is sent across the socket
            with lock:
                total_published += 1
        except Exception as e:
            with lock:
                failures += 1
            print(f"Publish failed: {e}")
            break

    client.loop_stop()
    client.disconnect()


def run_benchmark():
    global start_time, end_time, total_published, total_received, failures

    print(f"Starting Benchmark against {BROKER}:{PORT}")
    print(f"Subscribers: {NUM_SUBSCRIBERS}")
    print(f"Publishers: {NUM_PUBLISHERS}")
    print(f"Messages per publisher: {MESSAGES_PER_PUBLISHER}")
    print(f"Total expected raw publishes: {NUM_PUBLISHERS * MESSAGES_PER_PUBLISHER}")

    expected_total_received = NUM_PUBLISHERS * MESSAGES_PER_PUBLISHER * NUM_SUBSCRIBERS
    print(f"Total expected received (pubs * msgs * subs): {expected_total_received}")

    # Start subscribers
    print("\n[1/3] Starting subscribers...")
    subs = []
    for i in range(NUM_SUBSCRIBERS):
        t = threading.Thread(target=subscriber_task, args=(f"bench-sub-{i}",))
        t.start()
        subs.append(t)

    print(
        "Waiting 2 seconds for subscribers to establish connection & subscriptions..."
    )
    time.sleep(2)

    # Start publishers
    print("\n[2/3] Starting publishers to hammer the broker...")
    pubs = []
    start_time = time.time()
    for i in range(NUM_PUBLISHERS):
        t = threading.Thread(target=publisher_task, args=(f"bench-pub-{i}",))
        t.start()
        pubs.append(t)

    # Wait for all publishers to finish
    for t in pubs:
        t.join()

    print("All publishers have finished sending.")

    # Wait a bit for messages to be delivered
    print("\n[3/3] Waiting for messages to propagate to subscribers...")
    last_received = -1
    stable_count = 0
    timeout_checks = 0

    # Wait until received count stops changing or we hit expected total
    while stable_count < 3 and timeout_checks < 15:
        time.sleep(1)
        timeout_checks += 1
        with lock:
            current = total_received

        if current == last_received:
            stable_count += 1
        else:
            last_received = current
            stable_count = 0

        if current >= expected_total_received:
            break

    end_time = time.time()
    duration = end_time - start_time

    # Calculate metrics
    loss = expected_total_received - total_received
    loss_pct = (
        (loss / expected_total_received) * 100 if expected_total_received > 0 else 0
    )
    throughput = (total_published + total_received) / duration

    print("\n====================================")
    print("📈 Benchmark Results")
    print("====================================")
    print(f"Time Taken:             {duration:.2f} seconds")
    print(f"Total Published:        {total_published}")
    print(f"Expected to Receive:    {expected_total_received}")
    print(f"Actually Received:      {total_received}")
    print(f"Connection/Pub Failures:{failures}")

    if loss > 0:
        print(f"Lost Packets:           {loss} ({loss_pct:.2f}%) ❌")
    else:
        print(f"Lost Packets:           0 (0.00%) ✅")

    print(f"Overall Throughput:     {throughput:.2f} messages/sec")
    print("====================================")

    # Note: We aren't cleanly shutting down the sub threads here to keep the script simple,
    # the process will just exit.


if __name__ == "__main__":
    run_benchmark()
