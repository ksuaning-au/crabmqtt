/**
 * Using this project to learn Rust.
 *
 */

#[derive(Debug, FromPrimitive, PartialEq)] // Lets us print stuff and copy using .clone()
#[repr(u8)]
pub enum PacketType {
    Connect = 1,
    ConnAck = 2,
    Publish = 3,
    PubAck = 4,
    PubRec = 5,
    PubRel = 6,
    PubComp = 7,
    Subscribe = 8,
    SubAck = 9,
    Unsubscribe = 10,
    UnsubAck = 11,
    PingReq = 12,
    PingResp = 13,
    Disconnect = 14,
    Auth = 15,
}

use num_derive::FromPrimitive;
use num_traits::FromPrimitive;
// use std::io::{Read, Write};
// use std::net::{TcpListener, TcpStream};

use std::collections::{HashMap, HashSet};
use std::sync::{Arc, RwLock};

use tokio::sync::mpsc; // Multi Producer Single Consumer
//
// struct Client {
//     sender: mpsc::Sender<Bytes>
// }
//
#[derive(Default)]
struct BrokerState {
    subscriptions: HashMap<String, HashSet<String>>, // topic -> client_id
    clients: HashMap<String, mpsc::Sender<Vec<u8>>>, // client_id -> Client (Mpsc sender)
}

use tokio::io::{AsyncReadExt, AsyncWriteExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Hello, world!");

    // let listener = TcpListener::bind("0.0.0.0:1883")?;

    let listener = tokio::net::TcpListener::bind("0.0.0.0:1883").await?;
    println!("MQTT Sock Started");

    let state = Arc::new(RwLock::new(BrokerState::default()));
    loop {
        let (mut stream, addr) = listener.accept().await?;
        println!("Client Connected: {}", addr);
        let state_clone = state.clone(); // Because of Arc share crap can't just pass ref so we
        // clone pointer.
        tokio::spawn(async move {
            handle_client(stream, state_clone).await;
        });
    }
    //
    // for stream in listener.incoming() {
    //     match stream {
    //         Ok(mut stream) => {
    //             println!("Client Connected: {:?}", stream.peer_addr()?);
    //             handle_client(&mut stream);
    //         }
    //         Err(e) => {
    //             eprintln!("Conn Failed! {}", e);
    //         }
    //     }
    // }
    println!("Program End.");
    Ok(())
}

fn extract_remaining_length(buffer: &[u8]) -> Result<(u32, usize), &'static str> {
    let length_section = &buffer[1..]; // Want the buffer starting after the packet type and flags.
    let mut payload_length: u32 = 0; // Size maxes out at 4 bytes so 32bit
    let mut multiplier: u32 = 1;
    let mut bytes_read = 0;

    for &byte in length_section {
        bytes_read += 1;
        // The 8th bit is used to indicate if length keeps going.
        payload_length += ((byte & 127) as u32) * multiplier;

        if (byte & 128) == 0 {
            let data_start_index = ((1 + bytes_read) as usize);
            return Ok((payload_length, data_start_index));
        }
        multiplier *= 128;
    }
    Err("My Error")
}

async fn handle_ping(tx: &mpsc::Sender<Vec<u8>>) {
    let pingresp = vec![0xD0, 0x00];
    if let Err(e) = tx.send(pingresp).await {
        eprintln!("Failed sending pingresp via channel: {}", e);
    }
}

fn parse_connect_client_id(buffer: &[u8]) -> Option<String> {
    let (_, data_start) = extract_remaining_length(buffer).ok()?;
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
    std::str::from_utf8(client_id_bytes)
        .ok()
        .map(|s| s.to_string())
}

async fn handle_connect(
    buffer: &[u8],
    state: &Arc<RwLock<BrokerState>>,
    tx: mpsc::Sender<Vec<u8>>,
) -> String {
    let connack = vec![0x20, 0x02, 0x00, 0x00];
    let client_id = parse_connect_client_id(buffer).unwrap();
    println!("{:?}", client_id);

    {
        //let mut state = state.write(); // Aquire write lock from RwLock
        let mut state = state.write().unwrap();
        // Add client Id and Sender to broker state.
        state.clients.insert(client_id.clone(), tx.clone());
    }

    if let Err(e) = tx.send(connack).await {
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

// fn parse_subscribe_topics(buffer: &[u8]) -> Option<(u16, Vec<(String, u8)>)> {
//     let (remaning_len, data_start) = extract_remaining_length(buffer).ok()?;
//     let packet_end = data_start + remaning_len as usize;

//     let mut pos = data_start;

//     if pos + 2 > packet_end {
//         println!("Invalid Packet Size!");
//         return None; // Invalid packet
//     }
//     // This apparently always there even with no QoS?
//     let packet_id = ((buffer[pos] as u16) << 8) | (buffer[pos + 1] as u16);
//     pos += 2;

//     let mut topics = Vec::new();

//     while pos < packet_end {
//         if pos + 2 > packet_end {
//             break;
//         }

//         let topic_len = (((buffer[pos] as u16) << 8) | (buffer[pos + 1] as u16)) as usize;
//         pos += 2;
//         println!("Pos: {} | Topic Len: {}", pos, topic_len);
//         let topic_bytes = &buffer[pos..pos + topic_len];
//         pos += topic_len;

//         if let Ok(topic_str) = std::str::from_utf8(topic_bytes) {
//             let qos = buffer[pos];
//             pos += 1;
//             topics.push((topic_str.to_string(), qos));
//         } else {
//             break;
//         }
//     }
//     return Some((packet_id, topics));
// }

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

async fn handle_subscribe(
    buffer: &[u8],
    client_id: &str,
    tx: &mpsc::Sender<Vec<u8>>,
    state: &Arc<RwLock<BrokerState>>,
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
    let _ = tx.send(suback).await;
}

async fn handle_publish(buffer: &[u8], state: &Arc<RwLock<BrokerState>>) {
    // The payload size is variable len to support large payloads so we need to
    // loop through it to find where data starts and payload size ends.
    let (payload_size, start_index) = match extract_remaining_length(&buffer) {
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

    println!("Publishing to Topic: {}", topic_str);
    // Get Subscribers
    let mut target_channels = Vec::new();
    {
        let state_read = state.read().unwrap();
        if let Some(subscribers) = state_read.subscriptions.get(&topic_str) {
            for client_id in subscribers {
                if let Some(tx) = state_read.clients.get(client_id) {
                    println!("Pushing Client ID to target Channels: {}", client_id);
                    target_channels.push(tx.clone()); // Just clone the sender!
                }
            }
        }
    }
    for tx in target_channels {
        tx.send(packet_bytes.to_vec()).await; // Safe!
    }
}

async fn handle_client(mut stream: tokio::net::TcpStream, state: Arc<RwLock<BrokerState>>) {
    println!("Handling Client");
    let mut current_client_id: Option<String> = None; // Gets set by CONNECT

    // Split sockets into halves so we can give ownership to bits that need it.
    let (mut rx_socket, mut tx_socket) = stream.into_split();

    let (tx, mut rx) = mpsc::channel::<Vec<u8>>(100);

    tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            println!("Send Message: {:?}", msg);
            if let Err(e) = tx_socket.write_all(&msg).await {
                eprintln!("Failed to write sock: {}", e);
                break;
            }
        }
    });
    

    /*
     * 1. Data Loads into Buffer
     * 2. We start reading buffer from cursor 0
     * 3. Extract packet and hnadle it.
     * 4. Loop until all packets in current buffer processed.
     * 5. Copy remaining bytes to start of buffer.
     * 6. Set cursor so socket reads new data into buffer after remaing bytes
     */
    let mut buffer = [0; 1024];
    // Need a cursor so when buffer has more than one packet inside we don't just process the first
    // one and throw away the rest.
    
    // Cursor inidcates where socket should begin writing (cursor is where any remaining data from
    // last packet ends)

    // So if we have 5 bytes of old packet the sock starts writing into buffer at index 5.
    let mut cursor = 0;
    loop {
        match rx_socket.read(&mut buffer[cursor..]).await {
            Ok(n) if n > 0 => {
                println!("Received {} bytes", cursor + n);

                let mut pos = 0;
                while pos < cursor + n {
                    
                    let (payload_size, data_start_index) = match extract_remaining_length(&buffer[pos..]).unwrap();

                    let packet_end = pos + data_start_index + payload_size as usize;
                    
                    // If end of the packet is bigger than the curosr (where buffer starts and th
                    // number of bytes we have recieved) break;
                    if packet_end > cursor + n {
                        break;
                    }

                    let packet = &buffer[pos..packet_end];

                    let packet_type = PacketType::from_u8(packet[0] >> 4);
                    if let Some(packet_type) = packet_type {
                        match packet_type {
                            PacketType::Connect => {
                                let id = handle_connect(packet, &state, tx.clone()).await;
                                current_client_id = Some(id);
                            }
                            PacketType::Publish => handle_publish(packet, &state).await,
                            PacketType::Subscribe => {
                                if let Some(ref cid) = current_client_id {
                                    handle_subscribe(packet, cid, &tx, &state).await;
                                }
                            }
                            PacketType::PingReq => handle_ping(&tx).await,
                            _ => println!("Unknown packet type"),
                        }
                    }

                    pos = packet_end;
                }
                
                // After we have dealt with all the packets in buffer
                // Any remmaining bytes we need to throw into next buffer.
                let remaining = n - pos;
                if remaining > 0 {
                    // This function copies (start_src..end_src, start_dest)
                    // So copy_within(5..10, 0) copies items 5-10 to 0-5
                    buffer.copy_within(pos..pos + remaining, 0);
                }
                cursor = remaining; 
            }
            Ok(_) => {
                println!("Client disconected.");
                break;
            }
            Err(e) => {
                eprintln!("Error Reading from sock: {}", e);
                break;
            }
        }
    }
}
