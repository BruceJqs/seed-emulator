# Creating new services

Services are special kinds of layers. One way to differentiate the regular layers and services layer is the way they make changes to the emulation. A regular Layer makes changes to the entire emulation (like BGP, which configure peeing across multiple different autonomous systems, exchanges, and routers). In contrast, a service only makes changes to individual nodes (like `Web`, which install `nginx` on the given node). 

In the old design, services are installed by providing the node object to the services. In the new design, we decided not to use any node object to identify which node to install the services on, as that creates dependencies to the base layer, as mentioned in the previous section. This design is also revised. In the new design, services do not directly install a web server on a physical host. Instead, services create virtual nodes and install services on them. Virtual nodes are not real nodes; consider them as a "blueprint" of a physical node. Services keeps track of changes made to each virtual node internally. Eventually, virtual nodes are mapped to physical nodes with the binding mechanism.

For details on how to create virtual nodes and binding, see example 00 (simple peering) and the "Virtual node binding & filtering" section of the manual. One does not actually need to know how to create and manage virtual nodes when creating a new service - all of the heavy liftings are handled by the `Service` class.

Before proceeding with this guide, please go over the "creating a new layer" guide first. This guide is going to cover the following topics:

- Implementing the `Server` interface.
- Implementing and working with the `Service` interface.
- Selecting IPv4/IPv6 addresses and formatting endpoints safely.

## IPv4/IPv6 address and endpoint rules

SEED remains IPv4-first by default. Existing calls to `Interface.getAddress()`
and `Network.getPrefix()` are IPv4 APIs and should keep that meaning in new
services. A service that needs IPv6 should use the explicit IPv6 accessors or
the shared helpers from `seedemu.core`.

Use the helper APIs instead of manually concatenating endpoint strings:

```python
from seedemu.core import (
    AddressFamily,
    formatHostPort,
    formatMultiaddr,
    formatUrl,
    getNodeAddress,
    getNodeAddresses,
    getNodePreferredAddress,
    normalizeAddressFamily,
)
```

Recommended patterns:

- Default service endpoint selection to `AddressFamily.IPv4` unless the service
  API explicitly asks for IPv6 or dual stack.
- Use `getNodeAddress(node, family, preferLocal=True)` or
  `getNodeAddresses(node)` when resolving a physical node to an address.
  These helpers prefer Local-network interfaces and can fall back to the first
  available service-network or other interface.
- Use `formatHostPort(host, port)` and `formatUrl(scheme, host, port, path)`
  for host/port or URL text. IPv6 literals require brackets in these forms.
  Prefer separate host and port arguments for new APIs; if a legacy value
  already carries a bracketed IPv6 authority such as `[2000::1]:8443`,
  `formatUrl()` preserves the authority and canonicalizes the literal. When a
  caller also supplies a separate port, the separate port is authoritative
  for legacy IPv4, DNS-name, and bracketed IPv6 authorities.
- Use `formatMultiaddr(host, port)` for IPFS/libp2p multiaddrs.
- Normalize public address-family inputs with `normalizeAddressFamily()` so
  aliases such as `ipv4`, `ip6`, `inet`, and `AF_INET6` behave consistently.
- Do not claim full service-level IPv6 support until the service has code,
  documentation, and a regression check showing that old IPv4 behavior is
  unchanged.

## Implementing the `Server` interface

The first step of creating a new service is to create a new class implementing the `Server` interface. The `Server` interface represents a server software running on a physical node. Only one method is required b the `Server` interface:

### `Server:install`

All server must implement this method. This call installs a service onto a physical node. One parameter, the reference to the physical node, will be passed in, and the method does not need to return anything. Generally, one will make changes to the physical node here. (e.g., call `node.addSoftware('some_software')`). For details on API on the `Node` class, refer to the API documentation. 

Other methods to configure the service should also be implemented in this class. For example, the `WebServer` class implements `WebServer::setPort` to allow changing the listening port number of the nginx web server. However, if a setting will be affecting all instances of servers, the method to change such a setting should be implemented directly in the `Service` class instead. 

## Implementing and working with the `Service` interface

After finish working with the `Server` class, one will also need to create a new class implementing the `Service` interface. The `Service` interface is derived from the `Layer` interface. `Service` interface will handle the virtual node resolving internally.

Only one method is required in the `Service` interface:

### `Service::_createServer`

All services must implement this method. This call takes no parameter, and should create and return an instance of the `Server` of the `Service` (the one created in the last section). This instance will eventually be returned to the user.

One may optionally implement the following methods to customize the configuration and render of a server:

### `Service::_doConfigure`

The `_doConfigure` method will be called to configure a server on a node (during the configuration stage). Two parameters will be passed in. The first is a reference to the physical node, and the second is the instance of the `Server` that has been bound to this node. The default implementation of this method is to just return when called. 

### `Service::_doInstall`

The `_doInstall` method will be called to install a server on a node (during the render stage). Two parameters will be passed in. The first is a reference to the physical node, and the second is the instance of the `Server` that has been bound to this node. The default implementation of this method is to call `server.install(node)`.

### Retrieving list of virtual nodes and physical nodes

It is possible to get a list of virtual node names and their corresponding server objects by calling `Service::getPendingTargets`. It will return a dictionary, where the keys are virtual node names, and the values are server objects.

To get a list of physical nodes, one may call `Service::getTargets`. Note that `getTargets` only work in the render stage, as virtual nodes are resolved in the configuration stage. It will return a set, where the elements are set of tuples of `(Server, Node)`.

### Change render and configuration behaviour 

Sometimes a service may need to do some extra configuration on the service itself as a whole. Examples of this are `DomainNameService` and  `CymruIpOriginService`.

`DomainNameService` needs to add NS records to zone files after the virtual nodes are bound to physical nodes since before that, it does not know what IP address the servers will have. This is done by overriding the `render` implementation. Remember that the `Service` is just a special kind of `Layer`, so it still has all methods from the `Layer` interface. Services can still add logics to the render method. Just remember to call `super().render(emulator)`, so that the service interface can handle the rest of the installation process. 

`CymruIpOriginService`, on the other hand, needs to collect IP addresses in the emulator, create a new zone in the DNS layer. It does so by overriding the `configure` method of the `Layer` interface and collect IP there. It also calls `super().configure(emulator)` so the servers are properly configured and bound to physical nodes.
