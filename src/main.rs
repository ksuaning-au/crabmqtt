#[derive(Debug)] // Lets us print stuff and copy using .clone()
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


#[derive(Debug)]
pub struct FixedHeader {
    pub packet_type: PacketType,
    pub flags: u8,
    pub remaining_length: usize
}


use std::net::{TcpListener, TcpStream};
use std::io::Read;

fn main() ->Result<(), Box<dyn std::error::Error>> {
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

fn handle_client(stream: &mut TcpStream){
    println!("Handling Client");

    let mut buffer = [0; 1024];

    match stream.read(&mut buffer){
        Ok(n) if n > 0 => {
            println!("Recieved {} bytes", n);
        }
        Ok(_) => println!("Client disconected."),
        Err(e) => eprintln!("Error Reading from sock: {}", e),
    }
}
