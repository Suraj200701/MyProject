"""
Local-development Redis substitute.

This machine has no admin rights to install a Windows Redis service, so for
LOCAL DEVELOPMENT ONLY we run `fakeredis`'s TCP server, which speaks the real
Redis wire protocol (RESP) on 127.0.0.1:6379. The application code talks to
it through the standard `redis` Python client exactly as it would talk to a
real Redis/production instance — nothing in application code is aware this
is fakeredis. Production deployments (see docker-compose.yml) use the real
`redis:7-alpine` image.

Usage:
    python scripts/run_local_redis.py
"""

from fakeredis import TcpFakeServer

if __name__ == "__main__":
    server_address = ("127.0.0.1", 6379)
    print(f"Starting fakeredis TCP server on {server_address[0]}:{server_address[1]} (dev only)")
    server = TcpFakeServer(server_address, server_type="redis")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping fakeredis server")
