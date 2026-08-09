from .SystemProfile import SystemProfile


class BaseSystem:
    """Built-in SeedEmu system profiles."""

    UBUNTU_20_04 = SystemProfile("ubuntu20.04")
    SEEDEMU_BASE = SystemProfile("seedemu-base", subset=UBUNTU_20_04)
    SEEDEMU_ROUTER = SystemProfile("seedemu-router", subset=SEEDEMU_BASE)
    SEEDEMU_ETHEREUM = SystemProfile("seedemu-ethereum", subset=SEEDEMU_BASE)
    SEEDEMU_ETHEREUM_LEGACY = SystemProfile(
        "seedemu-ethereum-legacy", subset=SEEDEMU_BASE
    )
    SEEDEMU_ETHEREUM_POS = SystemProfile(
        "seedemu-ethereum-pos", subset=SEEDEMU_BASE
    )
    SEEDEMU_MONERO = SystemProfile("seedemu-monero", subset=SEEDEMU_BASE)
    SEEDEMU_SOLANA = SystemProfile("seedemu-solana", subset=SEEDEMU_BASE)
    SEEDEMU_OP_STACK = SystemProfile("seedemu-op-stack", subset=SEEDEMU_BASE)
    SEEDEMU_SC_DEPLOYER = SystemProfile(
        "seedemu-sc-deployer", subset=SEEDEMU_BASE
    )
    SEEDEMU_CHAINLINK = SystemProfile("seedemu-chainlink", subset=SEEDEMU_BASE)
    DEFAULT = SEEDEMU_BASE
