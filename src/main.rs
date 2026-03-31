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


use std::sync::{Arc, RwLock};
use std::collections::{HashMap, HashSet};

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

    for &byte in buffer{
        bytes_read += 1;
        // The 8th bit is used to indicate if length keeps going.
        payload_length = ((byte & 127) as u32) * multiplier;
        
        if(byte & 128) == 0{
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
    std::str::from_utf8(client_id_bytes).ok().map(|s| s.to_string())
}

async fn handle_connect(buffer: &[u8], state: &Arc<RwLock<BrokerState>>, tx: mpsc::Sender<Vec<u8>>){
    let connack = vec![0x20, 0x02, 0x00, 0x00]; 
    let client_id = parse_connect_client_id(buffer).unwrap();
    println!("{:?}", client_id);
    
    {
        //let mut state = state.write(); // Aquire write lock from RwLock
        let mut state = state.write().unwrap();
        state.clients.insert(client_id.clone(), tx.clone());
    }

    if let Err(e) = tx.send(connack).await {
        eprintln!("Failed sending connack via channel: {}", e);
    }
    // Byte 0: packet type (2) and flags
    // Byte 1: Remaining Length  2 bytes (0x02)
    // Byte 2: Ack Flags (Not implemeted)
    // Byte 3: Return Code (0 for success)
    
    // match stream.write_all(&connack).await {
    //     Ok(()) => println!("Sent ConnAck: {:?}", client_id),
    //     Err(e) => eprintln!("Failed sending connack: {}", e),
    // };

}

async fn handle_subscribe(tx: &mpsc::Sender<Vec<u8>>, num_topics: u8) {
    let suback = vec![0x90, (0x02 + num_topics), 0x00, 0x00, 0x00];
    if let Err(e) = tx.send(suback).await {
        eprintln!("Failed sending suback via channel: {}", e);
    }
}


async fn handle_publish(buffer: &[u8]){
    // The payload size is variable len to support large payloads so we need to
    // loop through it to find where data starts and payload size ends.
    let (payload_size, start_index) = match extract_remaining_length(&buffer){
        Ok((payload_size, start_index)) => (payload_size, start_index),
        Err(e) => {
            eprintln!("Invalid Packet: {}", e);
            return;
        }
    };
    let mut current_pos = start_index;
    // Topci name len maxes out a 2 bytes (not variable like payload)
    let topic_len = ((buffer[current_pos] as usize) << 8) | (buffer[current_pos + 1] as usize);
    current_pos += 2;
    let topic_name = &buffer[current_pos..current_pos + topic_len];
    match std::str::from_utf8(topic_name){
        Ok(text) => println!("Topic: {}", text),
        Err(e) => eprintln!("Failed to decode topic {}", e),
    }
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

}

async fn handle_client(mut stream: tokio::net::TcpStream, state: Arc<RwLock<BrokerState>>){
    println!("Handling Client");
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

    let mut buffer = [0; 1024];
    loop {
        match rx_socket.read(&mut buffer).await {
            Ok(n) if n > 0 => {
                println!("Recieved {} bytes", n);
                let packet_type = PacketType::from_u8(buffer[0] >> 4);
                if let Some(packet_type) = packet_type {
                    println!("Packet Type: {:?}", packet_type);
                    match packet_type {
                        PacketType::Connect => handle_connect(&buffer, &state, tx.clone()).await,
                        PacketType::Publish => handle_publish(&buffer).await,
                        PacketType::Subscribe => handle_subscribe(&tx, 1).await,
                        PacketType::PingReq => handle_ping(&tx).await,
                        _ => println!("Unknown packet type"),
                    }
                } else {
                    println!("Unexpected packet type!");
                }
            }
            Ok(_) => {
                println!("Client disconected.");
                break;
            },
            Err(e) => {
                eprintln!("Error Reading from sock: {}", e);
                break;
            },
        }
    }
}
