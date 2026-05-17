use std::collections::{HashMap, HashSet};
use tokio::sync::mpsc;

#[derive(Default)]
pub struct BrokerState {
    pub subscriptions: HashMap<String, HashSet<String>>, // topic -> client_id
    pub clients: HashMap<String, mpsc::Sender<Vec<u8>>>, // client_id -> Client (Mpsc sender)
}

impl BrokerState {
    pub fn add_client(&mut self, id: String, tx: mpsc::Sender<Vec<u8>>) {
        self.clients.insert(id, tx);
    }
}
