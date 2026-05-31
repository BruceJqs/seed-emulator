# User Manual: Internet Exchange 


<a id="default-settings"></a>
## Default Settings

In essence, an Internet exchange is basically a high throughput LAN. 

- Name: The name for an Internet exchange 
is set to `ix{asn}`, where `{asn}` is the autonomous system number of 
the Internet exchange. For example, for an Internet exchange with ASN=100, 
the name is set to `ix100`. This naming mechanism is fixed for now. 

- Network prefix: The default network prefix for an IX is set to 
  `10.{asn}.0.0/24`. However, users can override this default 
  setting using the `prefix` parameter when creating an IX. 
  ```python
  ix100 = base.createInternetExchange(100, prefix='192.168.10.0/24')
  ```

- IPv6 prefix: IX peering LANs stay IPv4-only by default. If optional IPv6 is
  enabled on `Base`, each IX peering LAN receives a stable `/64` from the
  configured IPv6 root prefix. Users can override or disable the IX IPv6 prefix
  independently from the IPv4 prefix.
  ```python
  base = Base(enableIpv6=True)
  ix100 = base.createInternetExchange(100)
  ix200 = base.createInternetExchange(200, ipv6Prefix='2000:8:0:200::/64')
  ix201 = base.createInternetExchange(201, ipv6Prefix=None)
  ```

Route-server IPv6 addressing follows the same `rsIpv6Address` intent used by
node attachments. The default is `"auto"` when the IX has an IPv6 prefix.
See [IPv6 dual-stack emulation](./ipv6.md) for the full address plan.


<a id="customization"></a>
## Customization


```python
ix100 = base.createInternetExchange(100)
ix101 = base.createInternetExchange(101)

# Customize names (for visualization purpose)
ix100.getPeeringLan().setDisplayName('New York-100')
ix101.getPeeringLan().setDisplayName('Los Angeles-101')
```
