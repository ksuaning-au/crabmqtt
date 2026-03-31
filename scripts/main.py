import paho.mqtt.client as mqtt
import time
import threading


NUM_CLIENTS = 10
PUBLISH_INTERVAL = 1


def create_client(client_id: int):
    mqttc = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=f"test-client-{client_id}"
    )

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"Client {client_id}: Connected with result code {reason_code}")

    mqttc.on_connect = on_connect
    mqttc.connect("localhost", 1883, 60)
    mqttc.loop_start()
    return mqttc


def publish_loop(client_id: int, mqttc):
    topic = f"test/client{client_id}"
    count = 0
    while True:
        payload = f"client-{client_id}-msg-{count}"
        mqttc.publish(topic, payload)
        print(f"Client {client_id}: published to {topic}: {payload}")
        count += 1
        time.sleep(PUBLISH_INTERVAL)


def main():
    clients = []
    threads = []

    print(f"Starting {NUM_CLIENTS} clients...")
    for i in range(NUM_CLIENTS):
        mqttc = create_client(i)
        clients.append(mqttc)

        t = threading.Thread(target=publish_loop, args=(i, mqttc))
        t.daemon = True
        t.start()
        threads.append(t)

    print(f"All {NUM_CLIENTS} clients running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping clients...")


if __name__ == "__main__":
    main()
