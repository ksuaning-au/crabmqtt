# Crab MQTT Broker

I've been meaning to teach myself rust for a while it is the project I am using to do that. 

There is close to zero chance I actually implement the entire 137 pages of the spec.

I will however probably build this out as a working base MQTT implementation.

Targeting MQTTv3.1.1 for now.

## What Works
You can connect (ALL flags are ignored currently) and recieve a CONNACK.

You can subscribe to topics and you will recieve messages (wildcards not implemented yet).

You can publish to topics.

Ping and ping response working so client can stay alive.


## Benchmark Results

Python benchmark was huge bottleneck - new rust benchmark.rs:
Time: 9.53s  Sent: 500000  Received: 5000000  Throughput: 524874 msg/s


