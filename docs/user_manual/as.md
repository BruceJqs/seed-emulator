# User Manual: Autonomous System

- [Create Simple Stub Autonomous Systems (example)](../../examples/A00-simple-as) 
- [Create Transit Autonomous System (example)](../../examples/A01-transit-as) 
- [The Default IP Prefix/Address Assignment for Networks/Hosts](#default-assignment-network-host)
- [Overwrite the Default Network Prefix Assignment](#overwrite-default-prefix)
- [Overwrite the Default IP addresses Assignment](#overwrite-default-host-ip)


<a id="default-assignment-network-host"></a>
## The Default IP Prefix/Address Assignment for Networks/Hosts

Inside the emulator, when we create a network or node (host or router),
default network prefix and IP address will be assigned to them. 
For networks inside an autonomous system or an Internet exchange, 
the default network prefix assignment uses the following scheme:

```
10.{asn}.{id}.0/24
```

The `asn` is the autonomous system number, and `{id}` is the nth network created. 
For example, for `AS150`, the first network is `10.150.0.0/24`, and the second one 
is `10.150.1.0/24`. For Internet exchanges, the `{id}` part is always `0`.
For example, the default prefix of `IX100` is `10.100.0.0/24`.

IPv6 is not enabled by default. When the base layer enables optional IPv6,
local AS networks also receive IPv6 prefixes. The default IPv6 root prefix is
`2000::/12`; each AS receives a stable `/48`, and each local network receives a
stable `/64` under that AS prefix. The old IPv4 methods keep returning IPv4
objects, so use `Network.getIpv6Prefix()` and `Interface.getIpv6Address()` for
IPv6 state. See [IPv6 dual-stack emulation](./ipv6.md) for the complete
addressing model.


When a node is added to a network, the IP address for the host
is assigned with `AddressAssignmentConstraint`.
The default constraints are as follow:

- Host nodes: from 71 to 99
- Router nodes: from 254 to 200
- Router nodes in internet exchange: ASN

For example, in AS-150, if a host node joins a local network, it's IP address
will be `10.150.0.71`; the next host joining the network will become
`10.150.0.72`. If a router joins a local network, it's IP address will be
`10.150.0.254`, and if the router joined an internet exchange network (say
IX100), it will be `10.100.0.150`.


<a id="overwrite-default-prefix"></a>
## Overwrite the Default Network Prefix Assignment

If the autonomous system number is greater than 255, 
the default network prefix assignment will not work. 
We can explicitly set the network prefix when creating a network. 


```python
# For the network in Internet exchanges
base.createInternetExchange(asn = 33108, prefix = '206.81.80.0/23')

# For the network in autonomous system
as350 = base.createAutonomousSystem(350)
as350.createNetwork(name='net0', prefix = '128.230.0.0/16')
```

IPv6 prefixes can be overridden independently from IPv4 prefixes:

```python
base = Base(enableIpv6=True)
as350 = base.createAutonomousSystem(350)
as350.createNetwork(name='net0', prefix='128.230.0.0/16', ipv6Prefix='2000:0:350::/64')
as350.createNetwork(name='v4only', prefix='128.231.0.0/16', ipv6Prefix=None)
```

<a name="overwrite-default-host-ip"></a>
## Overwrite the Default IP addresses Assignment

Sometimes the default IP address assignment does now work or we prefer to assign
some specific IP address to a host. For example, 
if the ASN is 350, when its BGP router joins a network in
an Internet exchange (say IX100), it cannot use the default IP address, because
according to the assignment scheme, the IP address would be 
`10.100.0.350`, which is not a valid IP address. Our `joinNetwork`
API does take an `address` argument, allowing users to explicitly 
provide an IP address: 

```python
as350.createRouter('router0').joinNetwork('net0').joinNetwork('ix100', '10.100.0.35')
```

For IPv6, keep the IPv4 address argument unchanged and use `ipv6Address`:

```python
as350.createRouter('router0').joinNetwork('ix100', address='10.100.0.35', ipv6Address='2000:8:0:100::350')
```

We may alternatively implement our own `AddressAssignmentConstraint` class
instead. Both `createInternetExchange` and `createNetwork` accept the `aac`
argument, which will alter the auto address assignment behavior. For details,
please refer to the API documentation.
