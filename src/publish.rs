use crate::packet;
use crate::state;

use std::sync::Arc;

pub async fn handle_publish(buffer: Arc<[u8]>, state: &Arc<state::BrokerState>) {
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
    //let packet_bytes = &buffer[..packet_end]; // The exact bytes to forward

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
    //let payload_bytes = &buffer[current_pos..];
    /* match std::str::from_utf8(payload_bytes) {
        Ok(text) => println!("Payload: {}", text),
        Err(e) => println!("Payload is binary or invalid UTF-8: {}", e),
    }
    */
    //println!("Publishing to Topic: {}", topic_str);
    // Get Subscribers
    let subscriber_ids: Vec<String> = state
        .subscriptions
        .get(&topic_str)
        .map(|s| s.iter().cloned().collect())
        .unwrap_or_default();

    let mut target_channels = Vec::with_capacity(subscriber_ids.len());
    for id in &subscriber_ids {
        if let Some(tx) = state.clients.get(id) {
            target_channels.push(tx.value().clone());
        }
    }
    let packet_data: Arc<[u8]> = buffer;

    for tx in target_channels {
        let _ = tx.send(packet_data.clone()).await;
    }
}
