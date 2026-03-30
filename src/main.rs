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

fn get_packet_type(buffer: &[u8]) -> Option<PacketType> {
    PacketType::from_u8(buffer[0] >> 4)
}

#[derive(Debug)]
pub struct FixedHeader {
    pub packet_type: PacketType,
    pub flags: u8,
    pub remaining_length: usize,
}

use num_derive::FromPrimitive;
use num_traits::FromPrimitive;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Hello, world!");

    let listener = TcpListener::bind("0.0.0.0:1883")?;
    println!("MQTT Sock Started");

    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                println!("Client Connected: {:?}", stream.peer_addr()?);
                handle_client(&mut stream);
            }
            Err(e) => {
                eprintln!("Conn Failed! {}", e);
            }
        }
    }
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


fn handle_client(stream: &mut TcpStream) {
    println!("Handling Client");

    let mut buffer = [0; 1024];
    loop {
        match stream.read(&mut buffer) {
            Ok(n) if n > 0 => {
                println!("Recieved {} bytes", n);
                if let Some(packet_type) = PacketType::from_u8(buffer[0] >> 4) {
                    println!("Packet Type: {:?}", packet_type);
                    if packet_type == PacketType::Connect{
                        let connack = [0x20, 0x02, 0x00, 0x00]; 
                        // Byte 0: packet type (2) and flags
                        // Byte 1: Remaining Length  2 bytes (0x02)
                        // Byte 2: Ack Flags (Not implemeted)
                        // Byte 3: Return Code (0 for success)
                        match stream.write_all(&connack) {
                            Ok(()) => println!("Sent ConnAck"),
                            Err(e) => eprintln!("Failed sending connack: {}", e),
                        };
                    }else if packet_type == PacketType::Publish{
                        // The payload size is variable len to support large payloads so we need to
                        // loop through it to find where data starts and payload size ends.
                        let (payload_size, start_index) = match extract_remaining_length(&buffer){
                            Ok((payload_size, start_index)) => (payload_size, start_index),
                            Err(e) => {
                                eprintln!("Invalid Packet: {}", e);
                                break;
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
                } else{
                    println!("Unknown pack type");
                }
                // println!("Buffer: {:?}", buffer);
            }
            Ok(_) => println!("Client disconected."),
            Err(e) => eprintln!("Error Reading from sock: {}", e),
        }
    }
}
