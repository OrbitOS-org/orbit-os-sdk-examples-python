"""Hello web example: an app with a web page, opened from the Orbit OS Launcher.

The app listens on 127.0.0.1 only and registers the page with the Launcher.
The Launcher serves it at http://<device>/hello_web, asks for the device
login and forwards the requests to the app. Nothing is reachable from the
network without going through the Launcher.
"""
import argparse
import json
import os
import signal
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "hello_web"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# ROUTE is the path the Launcher serves the page at: http://<device>/hello_web.
ROUTE = "/hello_web"
# Web interface ports are reserved to the range PORT_MIN–PORT_MAX. The app
# starts at PREFERRED_PORT and moves to the next one when a port is taken.
PORT_MIN = 50000
PORT_MAX = 60000
PREFERRED_PORT = 50080

PAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "page.html")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a web page through the Orbit OS Launcher, behind the device login.")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Device IP address (development only; ignored when the app runs on the device)")
    args = parser.parse_args()

    app_manifest = metadata.must_parse_app_manifest_json(MANIFEST_PATH)
    meta = metadata.build(app_manifest)
    Logger.init(meta.name, "INFO", True)
    Logger.info(LOG_TAG, f"Starting {meta.name} v{meta.version}")
    app_manifest.print_info()

    # Stop cleanly on Ctrl+C, and on SIGTERM, which Orbit OS sends to stop an
    # app: both raise KeyboardInterrupt, which ends run.
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    try:
        client = Client.connect(args.host.strip())
    except FileNotFoundError as e:
        # Outside the device the SDK needs the development certificates, which
        # Orbit Studio puts in certs/grpc/ at the project root.
        Logger.fatal(LOG_TAG, f"Connect: certificate not found: {e}")
        return 1

    try:
        run(client)
    except (RuntimeError, grpc.RpcError) as e:
        Logger.fatal(LOG_TAG, error_text(e))
        return 1
    except KeyboardInterrupt:
        pass  # asked to stop: run has cleaned up
    finally:
        client.close()
    Logger.info(LOG_TAG, "Done.")
    return 0


def run(client: Client) -> None:
    # Read the values shown on the page once, at start-up.
    info = {
        "deviceName": client.system_manager.get_device_name(),
        "hardwareModel": client.system_manager.get_hardware_model(),
    }
    with open(PAGE_PATH, "rb") as f:
        page = f.read()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/info":
                body = json.dumps({**info, "time": datetime.now().astimezone().isoformat(timespec="seconds")})
                self._send(200, "application/json", body.encode())
            else:
                self._send(200, "text/html; charset=utf-8", page)

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            pass  # keep the app log for the app's own messages

    server = listen_and_register(client, Handler)
    host, port = server.server_address[:2]
    Logger.info(LOG_TAG, f"Listening on {host}:{port}, registered at {ROUTE}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        # Remove the page from the Launcher when the app stops.
        try:
            client.app_hub_manager.unregister_service()
        except grpc.RpcError as e:
            Logger.error(LOG_TAG, f"unregister_service: {error_text(e)}")


def listen_and_register(client: Client, handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    """Find a free port in the reserved range, starting at PREFERRED_PORT, and
    register the page with the Launcher. Return the server to serve on."""
    span = PORT_MAX - PORT_MIN + 1
    for i in range(span):
        port = PORT_MIN + (PREFERRED_PORT - PORT_MIN + i) % span
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError:
            continue  # port taken: try the next one
        resp = client.app_hub_manager.register_web_ui(f"127.0.0.1:{port}", ROUTE)
        if resp.error.code != 0:
            server.server_close()  # the Launcher refused this port: try the next one
            Logger.warn(LOG_TAG, f"register_web_ui 127.0.0.1:{port}: {resp.error.message}")
            continue
        return server
    raise RuntimeError(f"no free web interface port in {PORT_MIN}-{PORT_MAX}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
