# FROM golang:1.24.1 AS builder1
# ARG DEBIAN_FRONTEND=noninteractive
# WORKDIR /
# RUN git clone https://github.com/ethereum/go-ethereum
# RUN cd go-ethereum && git checkout v1.15.4 && make all

FROM rust:1.63 AS builder2
ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /
RUN apt-get update && apt-get -y --no-install-recommends install software-properties-common build-essential curl git gcc g++ make cmake pkg-config llvm-dev libclang-dev clang protobuf-compiler
RUN git clone https://github.com/wonkr/lighthouse.git
WORKDIR lighthouse
RUN git checkout stable
RUN make install
RUN make install-lcli
WORKDIR /

FROM handsonsecurity/seedemu-base

RUN apt-get update && apt-get install -y --no-install-recommends software-properties-common python3 python3-pip python3.12-venv

RUN python3 -m venv /app/venv

RUN /app/venv/bin/pip install web3
# Now, when running python scripts, use the python from the venv.
ENV PATH="/app/venv/bin:$PATH"
COPY  geth /usr/bin
COPY  bootnode /usr/bin
# COPY --from=builder1 /go-ethereum/build/bin/bootnode /usr/bin
COPY --from=builder2 /usr/local/cargo/bin/lcli /usr/bin
COPY --from=builder2 /usr/local/cargo/bin/lighthouse /usr/bin