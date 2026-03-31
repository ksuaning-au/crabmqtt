# Crab MQTT

I've been meaning to teach myself rust for a while it is the project I am using to do that. 

There is close to zero chance I actually implement the entire 137 pages of the spec.

I will however probably build this out as a working base MQTT implementation.


## What Works
You can connect (ALL flags are ignored currently) and recieve a CONNACK.

You can subscribe to topics and you will recieve messages (wildcards not implemented yet).

You can publish to topics.

Ping and ping response working so client can stay alive.

