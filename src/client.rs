use crate::connect;
use crate::packet;
use crate::ping;
use crate::publish;
use crate::state;
use crate::subscribe;

use std::sync::Arc;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::mpsc;

pub async fn handle_client_read(
    cursor: &mut usize,
    n: usize,
    buffer: &mut [u8],
    state: &Arc<state::BrokerState>,
    tx: &mpsc::Sender<Arc<[u8]>>,
    current_client_id: &mut Option<String>,
) {
    //println!("Received {} bytes", *cursor + n);

    let mut pos = 0;
    while pos < *cursor + n {
        let (payload_size, data_start_index) =
            match packet::extract_remaining_length(&buffer[pos..]) {
                Ok(result) => result,
                Err(e) => {
                    eprintln!("Invalid packet: {}", e);
                    break;
                }
            };

        let packet_end = pos + data_start_index + payload_size;

        // If end of the packet is bigger than the curosr (where buffer starts and th
        // number of bytes we have recieved) break;
        //

        // NOTE: This is actually valid. If we dont get all packet but do get length we
        // expect end of packet to be out of bounds....
        if packet_end > *cursor + n {
            break;
        }

        let packet = &buffer[pos..packet_end];

        let packet_type = packet::PacketType::from_u8(packet[0] >> 4);
        if let Some(packet_type) = packet_type {
            match packet_type {
                packet::PacketType::Connect => {
                    let id = connect::handle_connect(packet, &state, tx.clone()).await;
                    *current_client_id = Some(id);
                }
                packet::PacketType::Publish => {
                    let packet_data: Arc<[u8]> = Arc::from(&buffer[pos..packet_end]);
                    publish::handle_publish(packet_data, state).await;
                }
                packet::PacketType::Subscribe => {
                    if let Some(cid) = current_client_id {
                        subscribe::handle_subscribe(packet, cid, tx, state).await;
                    }
                }
                packet::PacketType::PingReq => ping::handle_ping(&tx).await,
                _ => println!("Unknown packet type"),
            }
        }

        pos = packet_end;
    }

    // After we have dealt with all the packets in buffer
    // Any remmaining bytes we need to throw into next buffer.
    //let remaining = if pos > n { 0 } else { n - pos };
    let total = *cursor + n;
    let remaining = total.saturating_sub(pos);
    if remaining > 0 {
        // This function copies (start_src..end_src, start_dest)
        // So copy_within(5..10, 0) copies items 5-10 to 0-5
        buffer.copy_within(pos..pos + remaining, 0);
    }
    *cursor = remaining;
}

pub async fn handle_client(stream: tokio::net::TcpStream, state: Arc<state::BrokerState>) {
    println!("Handling Client");
    let mut current_client_id: Option<String> = None; // Gets set by CONNECT

    // Split sockets into halves so we can give ownership to bits that need it.
    let (mut rx_socket, mut tx_socket) = stream.into_split();

    let (tx, mut rx) = mpsc::channel::<Arc<[u8]>>(16384);

    tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            // println!("Send Message: {:?}", msg);
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
    let mut buffer = [0; 16384];
    // Need a cursor so when buffer has more than one packet inside we don't just process the first
    // one and throw away the rest.

    // Cursor inidcates where socket should begin writing (cursor is where any remaining data from
    // last packet ends)

    // So if we have 5 bytes of old packet the sock starts writing into buffer at index 5.
    let mut cursor = 0;
    loop {
        match rx_socket.read(&mut buffer[cursor..]).await {
            Ok(n) if n > 0 => {
                handle_client_read(
                    &mut cursor,
                    n,
                    &mut buffer,
                    &state,
                    &tx,
                    &mut current_client_id,
                )
                .await;
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
