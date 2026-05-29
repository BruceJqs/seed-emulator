# SEED Agent Benchmarks

This directory contains reusable SeedAgent benchmark packages. A package is not
just a mission prompt. It defines runtime setup, normal state, fault injection,
allowed observations/actions, oracle checks, scoring, and replay artifacts.

## Package Families

- `incident.*`: real Internet incident replay
- `sandbox.*`: project deployment sandbox
- `ctf.*`: CTF / AI attack-defense scenario
- `rb.*`: red/blue operational drill
- `perm.*`: restricted-permission benchmark variant

## First Package

```text
incident.bgp_route_leak_optimizer.v1/
```

This package is the first implementation target because SEED can already model
AS boundaries, BGP path changes, client probes, and scoped routing repairs.

## Expected Run Loop

```text
generate runtime -> collect baseline -> inject fault -> attach agent
  -> collect evidence -> propose repair -> gate action -> repair
  -> verify -> score -> write replay
```

The package skeleton is machine-readable planning material. Runtime adapters,
injectors, and scorers should be added incrementally.
