from .SystemProfile import SystemProfile


class BaseSystem:
    """Built-in SeedEmu system profiles."""

    UBUNTU_20_04 = SystemProfile("ubuntu20.04")
    SEEDEMU_BASE = SystemProfile("seedemu-base")
    SEEDEMU_ROUTER = SystemProfile("seedemu-router")
    SEEDEMU_ETHEREUM = SystemProfile("seedemu-ethereum")
    SEEDEMU_ETHEREUM_LEGACY = SystemProfile("seedemu-ethereum-legacy")
    SEEDEMU_ETHEREUM_POS = SystemProfile("seedemu-ethereum-pos")
    SEEDEMU_MONERO = SystemProfile("seedemu-monero")
    SEEDEMU_SOLANA = SystemProfile("seedemu-solana")
    SEEDEMU_OP_STACK = SystemProfile("seedemu-op-stack")
    SEEDEMU_SC_DEPLOYER = SystemProfile("seedemu-sc-deployer")
    SEEDEMU_CHAINLINK = SystemProfile("seedemu-chainlink")
    DEFAULT = SEEDEMU_BASE
