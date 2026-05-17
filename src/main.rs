mod client;
/**
 * Using this project to learn Rust.
 *
 */
mod connect;
mod packet;
mod ping;
mod publish;
mod state;
mod subscribe;

use std::sync::Arc;

use tokio::io::{AsyncReadExt, AsyncWriteExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let listener = tokio::net::TcpListener::bind("0.0.0.0:1883").await?;
    println!("MQTT Sock Started");

    let state = Arc::new(state::BrokerState::default());
    loop {
        let (mut stream, addr) = listener.accept().await?;
        println!("Client Connected: {}", addr);
        let state_clone = state.clone(); // Because of Arc share crap can't just pass ref so we
        // clone pointer.
        tokio::spawn(async move {
            client::handle_client(stream, state_clone).await;
        });
    }
}
