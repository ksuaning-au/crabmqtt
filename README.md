# Crab MQTT Broker

I've been meaning to teach myself rust for a while it is the project I am using to do that. 

There is close to zero chance I actually implement the entire 137 pages of the spec.

I will however probably build this out as a working base MQTT implementation.


## What Works
You can connect (ALL flags are ignored currently) and recieve a CONNACK.

You can subscribe to topics and you will recieve messages (wildcards not implemented yet).

You can publish to topics.

Ping and ping response working so client can stay alive.


## Benchmark Results

Results from benchmark.py

| Metric | Value |
|--------|-------|
| Time Taken | 4.53 seconds |
| Total Published | 10000 |
| Expected to Receive | 50000 |
| Actually Received | 50000 |
| Connection/Pub Failures | 0 |
| Lost Packets | 0 (0.00%) ✅ |
| Overall Throughput | 13231.23 messages/sec |


