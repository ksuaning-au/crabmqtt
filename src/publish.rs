use std::sync::{Arc, RwLock};

use crate::packet;
use crate::state;

pub async fn handle_publish(buffer: &[u8], state: &Arc<RwLock<state::BrokerState>>) {
    // The payload size is variable len to support large payloads so we need to
    // loop through it to find where data starts and payload size ends.
    let (payload_size, start_index) = match packet::extract_remaining_length(&buffer) {
        Ok((payload_size, start_index)) => (payload_size, start_index),
        Err(e) => {
            eprintln!("Invalid Packet: {}", e);
            return;
        }
    };
    let packet_end = start_index + payload_size as usize;
    let packet_bytes = &buffer[..packet_end]; // The exact bytes to forward

    let mut current_pos = start_index;
    // Topci name len maxes out a 2 bytes (not variable like payload)
    let topic_len = ((buffer[current_pos] as usize) << 8) | (buffer[current_pos + 1] as usize);
    current_pos += 2;
    let topic_name = &buffer[current_pos..current_pos + topic_len];
    let topic_str = match std::str::from_utf8(topic_name) {
        Ok(text) => text.to_string(),
        Err(_) => return,
    };

    current_pos += topic_len;
    let qos = (buffer[0] & 0x06) >> 1;
    if qos > 0 {
        current_pos += 2; // Skip the 2-byte Packet ID
    }
    let payload_bytes = &buffer[current_pos..];
    match std::str::from_utf8(payload_bytes) {
        Ok(text) => println!("Payload: {}", text),
        Err(e) => println!("Payload is binary or invalid UTF-8: {}", e),
    }

    //println!("Publishing to Topic: {}", topic_str);
    // Get Subscribers
    let mut target_channels = Vec::new();
    {
        let state_read = state.read().unwrap();
        if let Some(subscribers) = state_read.subscriptions.get(&topic_str) {
            for client_id in subscribers {
                if let Some(tx) = state_read.clients.get(client_id) {
                    // println!("Pushing Client ID to target Channels: {}", client_id);
                    target_channels.push(tx.clone()); // Just clone the sender!
                }
            }
        }
    }
    for tx in target_channels {
        if let Err(e) = tx.send(packet_bytes.to_vec()).await {
            eprintln!("Failed to forward to subscriber");
        }
    }
}
