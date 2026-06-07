FROM handsonsecurity/seedemu-multiarch-router:buildx-latest

ARG DEBIAN_FRONTEND=noninteractive
RUN mkdir -p /usr/share/doc/bird2/examples/ \
    && touch /usr/share/doc/bird2/examples/bird.conf \
    && apt-get update \
    && apt-get install -y --no-install-recommends bind9 nginx-light iptables \
    && rm -rf /var/lib/apt/lists/*
