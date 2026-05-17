use std::collections::HashSet;
use std::sync::Arc;
use tokio::sync::mpsc;

use dashmap::DashMap; // Async optimised hashmap - removes need for RWlock..

#[derive(Default)]
pub struct BrokerState {
    pub subscriptions: DashMap<String, HashSet<String>>,
    pub clients: DashMap<String, mpsc::Sender<Arc<[u8]>>>,
}
