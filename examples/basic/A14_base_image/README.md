# Platform-aware Base Image

This example assigns separate AMD64 and ARM64 OCI image references to one
SeedEmu host. The Docker compiler selects the reference matching its target
platform while ordinary nodes continue to use their existing `BaseSystem`.

Compile locally with the standard example runner:

```bash
python seedemu/testing/cli.py compile examples/basic/A14_base_image/example.yaml
```

Run the Docker lifecycle and image contract checks:

```bash
python seedemu/testing/cli.py all examples/basic/A14_base_image/example.yaml
```

The full test checks AMD64 output and the running container. Its test program
also compiles an ARM64 variant, verifies image reference parsing and validation,
checks the missing-platform error, and confirms the legacy base-system fallback.
