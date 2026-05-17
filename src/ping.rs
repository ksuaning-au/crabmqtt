use tokio::sync::mpsc;

use std::sync::Arc;

pub async fn handle_ping(tx: &mpsc::Sender<Arc<[u8]>>) {
    let pingresp = vec![0xD0, 0x00];
    if let Err(e) = tx.send(pingresp.into()).await {
        eprintln!("Failed sending pingresp via channel: {}", e);
    }
}
