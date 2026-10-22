#!/usr/bin/env bash
# Print which DNS servers answer from inside WSL.
ls -l /etc/resolv.conf
cat /etc/resolv.conf
for server in 1.1.1.1 8.8.8.8 10.255.255.254; do
  printf '%s: ' "$server"
  timeout 6 python3 - "$server" <<'PY' || echo timeout
import socket, sys
query = bytes.fromhex("123401000001000000000000") + b"\x06github\x03com\x00\x00\x01\x00\x01"
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(4)
sock.sendto(query, (sys.argv[1], 53))
print(len(sock.recvfrom(512)[0]), "bytes")
PY
done
