use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::mpsc;

#[derive(Default)]
pub struct BrokerState {
    pub subscriptions: HashMap<String, HashSet<String>>, // topic -> client_id
    pub clients: HashMap<String, mpsc::Sender<Arc<[u8]>>>, // client_id -> Client (Mpsc sender)
}

impl BrokerState {
    pub fn add_client(&mut self, id: String, tx: mpsc::Sender<Arc<[u8]>>) {
        self.clients.insert(id, tx);
    }
}
