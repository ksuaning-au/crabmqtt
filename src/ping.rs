use tokio::sync::mpsc;

pub async fn handle_ping(tx: &mpsc::Sender<Vec<u8>>) {
    let pingresp = vec![0xD0, 0x00];
    if let Err(e) = tx.send(pingresp).await {
        eprintln!("Failed sending pingresp via channel: {}", e);
    }
}
