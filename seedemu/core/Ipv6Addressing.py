from __future__ import annotations

from ipaddress import IPv6Network
from typing import Dict, Set


class Ipv6Addressing:
    """Deterministic IPv6 prefix allocator for optional dual-stack emulations."""

    def __init__(self, rootPrefix: str = "2000::/12"):
        self.__root = IPv6Network(rootPrefix)
        assert self.__root.prefixlen <= 48, "IPv6 root prefix must be /48 or shorter"
        self.__used_as_indices: Set[int] = set()
        self.__as_prefixes: Dict[int, IPv6Network] = {}
        self.__as_net_indices: Dict[int, int] = {}
        self.__ix_prefixes: Dict[int, IPv6Network] = {}
        self.__ix_indices: Set[int] = set()
        self.__allocated_prefixes: Set[IPv6Network] = set()
        self.__as_prefix_bits = 48 - self.__root.prefixlen
        self.__network_bits = 16
        self.__ix_base = 1 << max(self.__as_prefix_bits - 1, 0)

    def getRootPrefix(self) -> IPv6Network:
        return self.__root

    def __prefix_from_index(self, index: int, prefixlen: int) -> IPv6Network:
        child_bits = prefixlen - self.__root.prefixlen
        assert child_bits >= 0, "child prefix must be within IPv6 root"
        assert index >= 0 and index < (1 << child_bits), "IPv6 prefix index out of root range"
        base = int(self.__root.network_address)
        shift = 128 - prefixlen
        return IPv6Network((base + (index << shift), prefixlen))

    def __is_available(self, prefix: IPv6Network) -> bool:
        return all(not prefix.overlaps(used) for used in self.__allocated_prefixes)

    def __claim_index(self, preferred: int, used: Set[int], limit: int, prefixlen: int) -> int:
        assert limit > 0, "IPv6 root prefix does not have enough allocation space"
        index = preferred % limit
        while index in used or not self.__is_available(self.__prefix_from_index(index, prefixlen)):
            index = (index + 1) % limit
            assert index != preferred % limit, "IPv6 prefix allocation exhausted"
        used.add(index)
        return index

    def assignAsPrefix(self, asn: int) -> IPv6Network:
        if asn not in self.__as_prefixes:
            limit = 1 << self.__as_prefix_bits
            preferred = int(asn)
            index = self.__claim_index(preferred, self.__used_as_indices, limit, 48)
            self.__as_prefixes[asn] = self.__prefix_from_index(index, 48)
            self.__allocated_prefixes.add(self.__as_prefixes[asn])
            self.__as_net_indices[asn] = 0
        return self.__as_prefixes[asn]

    def nextAsNetworkPrefix(self, asn: int) -> IPv6Network:
        as_prefix = self.assignAsPrefix(asn)
        index = self.__as_net_indices.get(asn, 0)
        assert index < (1 << self.__network_bits), "IPv6 /64 network allocation exhausted for AS{}".format(asn)
        self.__as_net_indices[asn] = index + 1
        base = int(as_prefix.network_address)
        return IPv6Network((base + (index << 64), 64))

    def assignIxPrefix(self, ixid: int) -> IPv6Network:
        if ixid not in self.__ix_prefixes:
            child_bits = 64 - self.__root.prefixlen
            limit = 1 << child_bits
            preferred = (self.__ix_base + int(ixid)) % limit
            index = self.__claim_index(preferred, self.__ix_indices, limit, 64)
            self.__ix_prefixes[ixid] = self.__prefix_from_index(index, 64)
            self.__allocated_prefixes.add(self.__ix_prefixes[ixid])
        return self.__ix_prefixes[ixid]
