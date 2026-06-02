from __future__ import annotations

from typing import Set, Tuple

from seedemu.core import Emulator, Layer, Router, ScopedRegistry


class FrrBgp(Layer):
    """Compatibility shim for the old FRR layer API.

    FRR is now a Router routing backend. New topologies should use
    createRouter(..., routingBackend="frr"). This layer only keeps older
    examples working by setting the selected router backend before Routing
    renders daemon configuration.
    """

    __enabled: Set[Tuple[int, str]]

    def __init__(self):
        super().__init__()
        self.__enabled = set()
        self.addDependency("Routing", True, False)

    def getName(self) -> str:
        return "FrrBgp"

    def enableOn(self, asn: int, router_name: str) -> "FrrBgp":
        self.__enabled.add((int(asn), str(router_name)))
        return self

    def getEnabled(self) -> Set[Tuple[int, str]]:
        return set(self.__enabled)

    def configure(self, emulator: Emulator):
        reg = emulator.getRegistry()
        for asn, router_name in self.__enabled:
            scope = ScopedRegistry(str(asn), reg)
            assert scope.has("rnode", router_name), f"Router as{asn}/{router_name} not found for FrrBgp"
            router = scope.get("rnode", router_name)
            assert isinstance(router, Router)
            router.setRoutingBackend("frr")

    def render(self, emulator: Emulator):
        pass
