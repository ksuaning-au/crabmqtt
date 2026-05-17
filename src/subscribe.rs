use crate::state;
use std::collections::HashSet;
use std::sync::{Arc, RwLock};
use tokio::sync::mpsc;

fn parse_subscribe_topics(buffer: &[u8]) -> Option<(u16, Vec<(String, u8)>)> {
    let mut pos = 1;
    let mut multiplier = 1;
    let mut remaining_length = 0;

    while pos < buffer.len() {
        let byte = buffer[pos];
        remaining_length += ((byte & 127) as usize) * multiplier;
        pos += 1;
        if (byte & 128) == 0 {
            break;
        }
        multiplier *= 128;
    }

    let packet_end = pos + remaining_length;
    if packet_end > buffer.len() {
        return None;
    }
    if pos + 2 > packet_end {
        return None;
    }
    let packet_id = ((buffer[pos] as u16) << 8) | (buffer[pos + 1] as u16);
    pos += 2;
    let mut topics = Vec::new();

    while pos < packet_end {
        if pos + 2 > packet_end {
            break;
        }

        let topic_len = (((buffer[pos] as u16) << 8) | (buffer[pos + 1] as u16)) as usize;
        pos += 2;
        if pos + topic_len + 1 > packet_end {
            break;
        }
        let topic_bytes = &buffer[pos..pos + topic_len];
        pos += topic_len;
        if let Ok(topic_str) = std::str::from_utf8(topic_bytes) {
            let qos = buffer[pos];
            pos += 1;
            topics.push((topic_str.to_string(), qos));
        } else {
            break;
        }
    }

    return Some((packet_id, topics));
}

pub async fn handle_subscribe(
    buffer: &[u8],
    client_id: &str,
    tx: &mpsc::Sender<Arc<[u8]>>,
    state: &Arc<RwLock<state::BrokerState>>,
) {
    let (packet_id, topics_vec) = match parse_subscribe_topics(buffer) {
        Some(result) => result,
        None => {
            eprintln!("Failed to parse subscribe packet");
            return;
        }
    };
    // Scope it so we release write lock asap.
    {
        let mut state_write = state.write().unwrap();
        for (topic, qos) in &topics_vec {
            // Get the HashSet for this topic, or create an empty one if it doesn't exist
            println!("Client Id: {} | Sub to: {}", client_id, topic);
            let subscribers = state_write
                .subscriptions
                .entry(topic.clone())
                .or_insert_with(HashSet::new);
            subscribers.insert(client_id.to_string());
        }
    }
    let suback = vec![0x90, (0x02 + topics_vec.len() as u8), 0x00, 0x00, 0x00]; // Simplified SubAck
    let _ = tx.send(suback.into()).await;
}
