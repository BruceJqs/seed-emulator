FROM 98a2693c996c2294358552f48373498d
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip
RUN python3 -m pip install --no-cache-dir exabgp flask
COPY 082b96ec819c95ae773daebde675ef80 /start.sh
COPY d18858afc6bb66ec3a19d872077acfd2 /seedemu_sniffer
COPY 17ac2d812a99a91e7f747e1defb72a29 /seedemu_worker
RUN chmod +x /start.sh
RUN chmod +x /seedemu_sniffer
RUN chmod +x /seedemu_worker
COPY e01e36443f9f72c6204189260d0bd276 /ifinfo.txt
COPY d3d51fdf7f4bad30dc5db560a01ce629 /interface_setup
COPY 5ac7e724b120c7427f15933686d117e8 /opt/exabgp/event_sink.py
COPY 78f7fe8be8863a6a5f397f078dca49b7 /opt/exabgp/dashboard.py
COPY c332579e548f43a7a5f8e4414abc6ccd /etc/exabgp/exabgp.conf
CMD ["/start.sh"]

