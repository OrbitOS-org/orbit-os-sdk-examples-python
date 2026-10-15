# SPI example

List the SPI devices, read the configuration and run a full-duplex transfer.

An example app for [Orbit OS](https://www.orbit-os.org/?ref=github-sdk-examples-python), built with the [Orbit OS SDK for Python](https://github.com/OrbitOS-org/orbit-os-sdk-python). Part of the [Orbit OS examples for Python](../../README.md).

The pins, buses or ports used are constants at the top of `main.py`. Change them to match your board and wiring before you run.

## Run

Open **this folder** in VS Code with the [Orbit Studio](https://marketplace.visualstudio.com/items?itemName=orbit-os.orbit-studio) extension. You need **Python 3.13** and a device with Orbit OS in Developer Mode.

1. In the Orbit sidebar, run **Add / Update SDK** and set your device's IP. Orbit Studio downloads the SDK (`v26.0.3`) into `orbit-os-sdk-python/`.
2. Use **Run** to try it live: the example runs on your computer and talks to the device. The first time, Orbit Studio creates the `.venv` with Python 3.13 and installs the SDK in it.
3. Use **Build + Deploy** to install the signed `.orb` on the device.

The project runs against the SDK copy in `orbit-os-sdk-python/`, which is not in the repository: Orbit Studio downloads it. Without Orbit Studio, unpack the [SDK release](https://github.com/OrbitOS-org/orbit-os-sdk-python/releases/tag/v26.0.3) into that folder, put the development certificates in `certs/grpc/`, then:

```bash
uv venv --seed --python 3.13 .venv && uv pip install -e ./orbit-os-sdk-python
.venv/bin/python src/spi/main.py --host <device IP>
```

On Windows the interpreter is `.venv\Scripts\python`.

## Project layout

| Path | What |
|---|---|
| `src/spi/main.py` | the app |
| `src/spi/metadata.json` | manifest: name, version, entry point, permissions |
| `src/spi/requirements.txt` | extra pip packages bundled into the `.orb` (none here) |
| `src/spi/orb/icon.svg` | launcher icon |
| `orbit.project.json` | Orbit Studio project settings |

Permissions declared: `SystemService/*`, `SpiService/*`.
