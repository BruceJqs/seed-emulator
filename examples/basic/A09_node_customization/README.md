# Node customization

This example shows how to customize a physical `Node` before rendering and
compilation.

The example covers:

- selecting a runtime system with `setBaseSystem()`;
- installing software;
- adding Dockerfile build commands;
- importing and creating files;
- adding node start commands.

## Selecting a runtime system

Every node has a `SystemProfile`. By default, hosts use
`BaseSystem.DEFAULT`, which currently refers to `BaseSystem.SEEDEMU_BASE`.
Use `setBaseSystem()` when a node explicitly requires a different runtime
system:

```python
node.setBaseSystem(BaseSystem.UBUNTU_24_04)
```

`Node` stores only the compiler-neutral profile. During compilation, `Docker`
maps the exact profile to the corresponding image; in this example it selects
`ubuntu:24.04`.

Profiles may contain a less specialized profile according to the runtime image
inheritance chain:

```text
ubuntu:24.04
    └── seedemu-base:2.0
          └── seedemu-router:2.0
```

The relationship can be queried through the compatibility API:

```python
BaseSystem.doesAContainB(
    BaseSystem.SEEDEMU_ROUTER,
    BaseSystem.SEEDEMU_BASE,
)
```

This returns `True`. Binding and service configuration use the relationship to
keep the more specialized compatible profile. Image selection remains exact:
`seedemu-router` still maps to the router image rather than falling back to the
base image.

Extensions define their own `SystemProfile` values and may set `subset` to a
profile supplied by SeedEmu. SeedEmu does not need to contain the extension
profile or its Docker image mapping.

## Running the example

```bash
python node_customization.py --platform amd --output output
```

For ARM64:

```bash
python node_customization.py --platform arm --output output
```

The compile step also checks that the customized host generated a Dockerfile
starting with `FROM ubuntu:24.04`.
