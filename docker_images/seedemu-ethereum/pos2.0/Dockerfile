FROM ubuntu:24.04 AS builder1

ARG TARGETARCH

ENV DEBIAN_FRONTEND=noninteractive
ENV GOLANG_VERSION=1.24.0
ENV PATH="/usr/local/go/bin:$PATH"

WORKDIR /

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget git build-essential curl make python3 python3-pip ca-certificates \
    && apt-get clean

# Install Go manually
RUN curl -OL https://go.dev/dl/go${GOLANG_VERSION}.linux-${TARGETARCH}.tar.gz && \
    tar -C /usr/local -xzf go${GOLANG_VERSION}.linux-${TARGETARCH}.tar.gz && \
    rm go${GOLANG_VERSION}.linux-${TARGETARCH}.tar.gz

RUN go version  # Just to confirm installation


# Installing eth-beacon-genesis and eth2-val-tools
RUN git clone https://github.com/ethpandaops/eth-beacon-genesis.git  \
    && cd eth-beacon-genesis && git checkout 703e97aaa244eec4b077f974e01d02449e1ba2ba && make \
    && go install github.com/protolambda/eth2-val-tools@0d6d1ddb36479e73d7d876b29ac2d10ab3988e85

# Downloading geth 
RUN case "${TARGETARCH}" in amd64|arm64) ;; *) exit 1 ;; esac && \
    wget https://gethstore.blob.core.windows.net/builds/geth-linux-${TARGETARCH}-1.15.11-36b2371c.tar.gz && \
    tar -xzf geth-linux-${TARGETARCH}-1.15.11-36b2371c.tar.gz && \
    install -m 0755 geth-linux-${TARGETARCH}-1.15.11-36b2371c/geth /usr/local/bin/geth

# Downloading lighthouse
RUN case "${TARGETARCH}" in \
        amd64) LIGHTHOUSE_ARCH="x86_64" ;; \
        arm64) LIGHTHOUSE_ARCH="aarch64" ;; \
        *) exit 1 ;; \
    esac && \
    wget https://github.com/sigp/lighthouse/releases/download/v8.1.3/lighthouse-v8.1.3-${LIGHTHOUSE_ARCH}-unknown-linux-gnu.tar.gz && \
    tar -xzf lighthouse-v8.1.3-${LIGHTHOUSE_ARCH}-unknown-linux-gnu.tar.gz


FROM golang:1.18 AS builder2
ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /

# Build bootnode from go-ethereum v1.10.26 source
RUN go install github.com/ethereum/go-ethereum/cmd/bootnode@v1.10.26



# Final image    

FROM handsonsecurity/seedemu-base:2.0

RUN apt-get update && apt-get install -y --no-install-recommends software-properties-common python3 python3-pip
RUN python3 -m pip install --break-system-packages web3

COPY --from=builder1 /eth-beacon-genesis/bin/eth-beacon-genesis /usr/local/bin/eth-beacon-genesis
COPY --from=builder1 /root/go/bin/eth2-val-tools /usr/local/bin/eth2-val-tools
COPY --from=builder1 /usr/local/bin/geth /usr/local/bin/geth
COPY --from=builder1 /lighthouse /usr/local/bin/lighthouse

COPY --from=builder2 /go/bin/bootnode /usr/local/bin/bootnode
