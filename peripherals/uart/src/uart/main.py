"""UART example: open a serial port at 9600 8N1 and print what it receives,
until Ctrl+C.

The received bytes go to stdout as they arrive; the log lines go through the
SDK logger. In a terminal the two may interleave.

Set the constants below to match your device.
"""
import argparse
import os
import signal
import sys

import grpc

import metadata
from client import Client, UartConfig
from client.uart_manager import UART_FLOW_NONE, UART_PARITY_NONE, UART_STOPBITS_1
from logger import Logger

LOG_TAG = "uart"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# UART_PORT_NAME must match a name returned by list_ports.
UART_PORT_NAME = "ttyUSB0"
# UART_BAUD_RATE is the line speed.
UART_BAUD_RATE = 9600
# RX_CHUNK_SIZE is the most bytes received at once.
RX_CHUNK_SIZE = 256


def main() -> int:
    parser = argparse.ArgumentParser(description="Open a serial port and print what it receives.")
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
    uart = client.uart_manager

    ports = uart.list_ports()
    Logger.info(LOG_TAG, f"UART ports: {ports}")
    if UART_PORT_NAME not in ports:
        raise RuntimeError(f"port {UART_PORT_NAME} not found on this device (available: {ports})")

    Logger.info(LOG_TAG, f"Opening {UART_PORT_NAME} at {UART_BAUD_RATE} 8N1 (Ctrl+C to stop)")
    port = uart.open(UartConfig(
        port=UART_PORT_NAME,
        baudrate=UART_BAUD_RATE,
        data_bits=8,
        parity=UART_PARITY_NONE,
        stop_bits=UART_STOPBITS_1,
        flow_control=UART_FLOW_NONE,
    ))

    # Release the port when done: only one app can hold a UART port at a time.
    try:
        # Read the configuration back to confirm what the device applied.
        cfg = port.get_config()
        Logger.info(LOG_TAG, f"Active config: port={cfg.port} baud={cfg.baudrate} dataBits={cfg.data_bits} "
                             f"parity={cfg.parity.name} stopBits={cfg.stop_bits.name} flow={cfg.flow_control.name}")

        while True:
            try:
                # listen yields each chunk as it arrives.
                for chunk in port.listen(RX_CHUNK_SIZE):
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
            except grpc.RpcError as e:
                # The SDK ends each listen after 30 seconds: listen again.
                if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                    raise
    finally:
        try:
            port.close()
        except (RuntimeError, grpc.RpcError) as e:
            Logger.error(LOG_TAG, f"Close: {error_text(e)}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
