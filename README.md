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

## Test Driven Developement
Reading the spec was fairly tedious so just generated a test suite that I can use to check items off one by one.

Since the test suite might be AI garbage I will be checking spec at the same time it will just be a nicer way of keeping this chugging along to see the number of failing tests go down.

## Benchmark Results

Python benchmark was huge bottleneck - new rust benchmark.rs:
Time: 9.53s  Sent: 500000  Received: 5000000  Throughput: 524874 msg/s

Pretty impressed by 500,000 messages per second. Obviously will depend on PC but still, this benchmark was run on an old laptop.

Found that you can add cargo aliases so you can do cool stuff like `cargo benchmark`.

Which aliases to `cargo run --bin benchmark`.
```

```
