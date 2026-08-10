# Building Docker images

The maintained image sources live directly under `docker_images/`. The base,
router, and Ethereum POS 2.0 images support both `linux/amd64` and
`linux/arm64`; separate architecture directories are not required.

## Local builds

Build the base image before images that use it:

```bash
docker build -t handsonsecurity/seedemu-base:2.0 docker_images/seedemu-base
docker build -t handsonsecurity/seedemu-router:2.0 docker_images/seedemu-router
```

Docker automatically selects the current host architecture for these builds.

## Publishing multiarch images

Use a buildx builder to publish both supported platforms under one tag:

```bash
docker buildx build --platform linux/amd64,linux/arm64 --push -t handsonsecurity/seedemu-base:2.0 docker_images/seedemu-base
docker buildx build --platform linux/amd64,linux/arm64 --push -t handsonsecurity/seedemu-router:2.0 docker_images/seedemu-router
docker buildx build --platform linux/amd64,linux/arm64 --push -t handsonsecurity/seedemu-ethereum:pos2.0 docker_images/seedemu-ethereum/pos2.0
```

Other image directories may have their own version or platform requirements;
check their Dockerfiles before publishing them as multiarch images.
