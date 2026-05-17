use rumqttc::{AsyncClient, MqttOptions, QoS};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;
use tokio::time::sleep;

const BROKER: &str = "127.0.0.1";
const PORT: u16 = 1883;
const TOPIC: &str = "benchmark/test";
const NUM_PUBLISHERS: u64 = 5;
const NUM_SUBSCRIBERS: u64 = 10;
const MSGS_PER_PUBLISHER: u64 = 10000;
const PAYLOAD_LENGTH: usize = 1024;

async fn create_subscribers(received: Arc<AtomicU64>, index: u64) {
    let mut opts = MqttOptions::new(&format!("bench-sub-{index}"), BROKER, PORT);
    opts.set_keep_alive(std::time::Duration::from_secs(60));
    let (client, mut eventloop) = AsyncClient::new(opts, 100);
    client.subscribe(TOPIC, QoS::AtMostOnce).await.unwrap();
    loop {
        match eventloop.poll().await {
            Ok(rumqttc::Event::Incoming(rumqttc::Packet::Publish(_))) => {
                received.fetch_add(1, Ordering::Relaxed);
            }
            Ok(_) => {} // ignore
            Err(e) => {
                eprintln!("Sub {index} error: {e}");
                break;
            }
        }
    }
}

fn payload(client_id: u64, msg_num: u64, length: usize) -> String {
    // Want to test performance with large payloads..
    let base = format!("bench-pub-{client_id}-msg-{msg_num}-");
    let padding = length.saturating_sub(base.len());
    format!("{}{}", base, "x".repeat(padding))
}

async fn create_publishers(payload: Arc<str>, published: Arc<AtomicU64>, index: u64) {
    let mut opts = MqttOptions::new(&format!("bench-pub-{index}"), BROKER, PORT);
    opts.set_keep_alive(std::time::Duration::from_secs(60));
    opts.set_max_packet_size(1024 * 1024, 1024 * 1024);
    let (client, mut eventloop) = AsyncClient::new(opts, 1000);

    tokio::spawn(async move {
        loop {
            if eventloop.poll().await.is_err() {
                break;
            }
        }
    });

    for j in 0..MSGS_PER_PUBLISHER {
        //let payload = payload(index, j, PAYLOAD_LENGTH);
        client
            .publish(TOPIC, QoS::AtMostOnce, false, payload.as_bytes())
            .await
            .unwrap();
        published.fetch_add(1, Ordering::Relaxed);
    }
}

#[tokio::main]
async fn main() {
    let received = Arc::new(AtomicU64::new(0));

    for i in 0..NUM_SUBSCRIBERS {
        let received = received.clone();
        tokio::spawn(async move { create_subscribers(received, i).await });
    }

    sleep(std::time::Duration::from_secs(2)).await;

    let start = Instant::now();
    let total_msgs = NUM_PUBLISHERS * MSGS_PER_PUBLISHER;
    let published = Arc::new(AtomicU64::new(0));

    // Lets us create a payload of varying lengths to test.
    let payload: Arc<str> = Arc::from("x".repeat(PAYLOAD_LENGTH));
    for i in 0..NUM_PUBLISHERS {
        let published = published.clone();
        let payload = payload.clone();
        tokio::spawn(async move {
            create_publishers(payload, published, i).await;
        });
    }

    // Wait for all messages to arrive at subscribers
    let expected = NUM_PUBLISHERS * MSGS_PER_PUBLISHER * NUM_SUBSCRIBERS;
    loop {
        let rcvd = received.load(Ordering::Relaxed);
        if rcvd >= expected {
            break;
        }
        sleep(std::time::Duration::from_millis(1)).await;
    }

    let duration = start.elapsed();
    let sent = published.load(Ordering::Relaxed);
    let rcvd = received.load(Ordering::Relaxed);
    let expected_received = sent * NUM_SUBSCRIBERS;
    let dropped = expected_received.saturating_sub(rcvd);
    let drop_pct = dropped as f64 / expected_received as f64 * 100.0;
    println!(
        "Time: {:.2}s  Sent: {total_msgs}  Received: {rcvd}  Throughput: {:.0} msg/s",
        duration.as_secs_f64(),
        rcvd as f64 / duration.as_secs_f64()
    );
    println!("Dropped: {drop_pct}%");
}
