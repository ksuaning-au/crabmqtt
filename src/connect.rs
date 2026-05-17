use crate::packet;
use crate::state;
use std::sync::{Arc, RwLock};

use tokio::sync::mpsc; // Multi Producer Single Consumer

fn parse_connect_client_id(buffer: &[u8]) -> Option<String> {
    let (_, data_start) = packet::extract_remaining_length(buffer).ok()?;
    let mut pos = data_start;
    // Skip protocol name
    let proto_len = ((buffer[pos] as usize) << 8) | (buffer[pos + 1] as usize);
    pos += 2 + proto_len;
    // Skip protocol level (1) + connect flags (1) + keep alive (2)
    pos += 4;
    // Read client ID
    let client_id_len = ((buffer[pos] as usize) << 8) | (buffer[pos + 1] as usize);
    pos += 2;

    let client_id_bytes = &buffer[pos..pos + client_id_len];

    return std::str::from_utf8(client_id_bytes)
        .ok()
        .map(|s| s.to_string());
}

fn parse_connect_protocol(buffer: &[u8]) -> Option<String> {
    // Had extract client ID first this does a bunch of duplicated work.. TODO: Clean up
    let (_, data_start) = packet::extract_remaining_length(buffer).ok()?;
    let mut pos = data_start;

    let proto_len = ((buffer[pos] as usize) << 8) | (buffer[pos + 1] as usize);
    pos += 2;
    let proto_bytes = &buffer[pos..pos + proto_len];

    return std::str::from_utf8(proto_bytes).ok().map(|s| s.to_string());
}

pub async fn handle_connect(
    buffer: &[u8],
    state: &Arc<RwLock<state::BrokerState>>,
    tx: mpsc::Sender<Arc<[u8]>>,
) -> String {
    let mut result_code = 0x00;

    let protocol = parse_connect_protocol(buffer).unwrap();
    println!("{:?}", protocol);
    // Tidy this regection up;
    if protocol != "MQTT" {
        result_code = 0x01;
    }
    let client_id = parse_connect_client_id(buffer).unwrap();
    println!("{:?}", client_id);

    if result_code == 0x00 {
        //let mut state = state.write(); // Aquire write lock from RwLock
        let mut state = state.write().unwrap();
        // Add client Id and Sender to broker state.
        state.add_client(client_id.clone(), tx.clone());
    }

    let connack = vec![0x20, 0x02, 0x00, result_code];
    if let Err(e) = tx.send(connack.into()).await {
        eprintln!("Failed sending connack via channel: {}", e);
    }

    return client_id;
    // Byte 0: packet type (2) and flags
    // Byte 1: Remaining Length  2 bytes (0x02)
    // Byte 2: Ack Flags (Not implemeted)
    // Byte 3: Return Code (0 for success)

    // match stream.write_all(&connack).await {
    //     Ok(()) => println!("Sent ConnAck: {:?}", client_id),
    //     Err(e) => eprintln!("Failed sending connack: {}", e),
    // };
}

