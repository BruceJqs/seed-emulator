FROM 98a2693c996c2294358552f48373498d
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git make
RUN arch="$(dpkg --print-architecture)"; case "$arch" in amd64) go_arch=amd64 ;; arm64) go_arch=arm64 ;; *) echo "unsupported arch: $arch"; exit 1 ;; esac; curl -fsSL https://go.dev/dl/go1.22.12.linux-${go_arch}.tar.gz -o /tmp/go.tgz && rm -rf /usr/local/go && tar -C /usr/local -xzf /tmp/go.tgz && rm -f /tmp/go.tgz && ln -sf /usr/local/go/bin/go /usr/local/bin/go && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt
RUN git clone https://github.com/xddxdd/bird-lg-go /lg
RUN GOBIN=/usr/local/bin /usr/local/go/bin/go install github.com/kevinburke/go-bindata/go-bindata@v3.11.0
RUN PATH=/usr/local/go/bin:$PATH make -C /lg
COPY 082b96ec819c95ae773daebde675ef80 /start.sh
COPY d18858afc6bb66ec3a19d872077acfd2 /seedemu_sniffer
COPY 17ac2d812a99a91e7f747e1defb72a29 /seedemu_worker
RUN chmod +x /start.sh
RUN chmod +x /seedemu_sniffer
RUN chmod +x /seedemu_worker
COPY e01e36443f9f72c6204189260d0bd276 /ifinfo.txt
COPY d3d51fdf7f4bad30dc5db560a01ce629 /interface_setup
CMD ["/start.sh"]

