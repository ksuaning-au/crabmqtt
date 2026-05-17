use num_derive::FromPrimitive;
use num_traits::FromPrimitive;

#[derive(Debug, FromPrimitive, PartialEq)]
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

impl PacketType {
    pub fn from_u8(value: u8) -> Option<Self> {
        FromPrimitive::from_u8(value)
    }
}

pub fn extract_remaining_length(buffer: &[u8]) -> Result<(usize, usize), &'static str> {
    let length_section = &buffer[1..]; // Want the buffer starting after the packet type and flags.
    let mut payload_length: u32 = 0; // Size maxes out at 4 bytes so 32bit
    let mut multiplier: u32 = 1;
    let mut bytes_read = 0;

    for &byte in length_section {
        bytes_read += 1;
        // The 8th bit is used to indicate if length keeps going.
        payload_length += ((byte & 127) as u32) * multiplier;

        if (byte & 128) == 0 {
            let data_start_index = ((1 + bytes_read) as usize);
            return Ok((payload_length as usize, data_start_index));
        }
        multiplier *= 128;
    }
    return Err("My Error");
}
