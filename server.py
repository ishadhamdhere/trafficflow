
import json
import os
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))

LANES = {
    1: "North",
    2: "South",
    3: "East",
    4: "West"
}

VEHICLE_TYPES = {
    1: "Car",
    2: "Bus",
    3: "Bike"
}

engine = None
engine_lock = threading.Lock()


def start_engine():
    global engine

    executable = BASE_DIR / ("main.exe" if os.name == "nt" else "main")

    if not executable.is_file():
        raise FileNotFoundError(
            f"C engine executable not found: {executable}"
        )

    engine = subprocess.Popen(
        [str(executable), "server"],
        cwd=str(BASE_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        encoding="utf-8",
        bufsize=1
    )

    if engine.poll() is not None:
        raise RuntimeError("The C traffic engine failed to start.")


def send_to_engine(command):
    with engine_lock:
        if engine is None or engine.poll() is not None:
            raise RuntimeError("The C traffic engine is not running.")

        engine.stdin.write(command + "\n")
        engine.stdin.flush()

        response = engine.stdout.readline()

        if not response:
            raise RuntimeError("The C engine returned no response.")

        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "The C engine returned invalid JSON: " + response
            ) from exc


def get_state():
    return send_to_engine("STATUS")


def send_json(handler, data, status=200):
    body = json.dumps(data).encode("utf-8")

    handler.send_response(status)
    handler.send_header(
        "Content-Type", "application/json; charset=utf-8"
    )
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def normalize_lane(value):
    if isinstance(value, str):
        value = value.strip().title()
        if value in LANES.values():
            return list(LANES.keys())[
                list(LANES.values()).index(value)
            ]

    if isinstance(value, int) and not isinstance(value, bool):
        if value in LANES:
            return value

    raise ValueError(
        "Lane must be 1 (North), 2 (South), 3 (East), or 4 (West)."
    )


def normalize_vehicle_type(value):
    if isinstance(value, str):
        value = value.strip().title()
        for number, name in VEHICLE_TYPES.items():
            if value == name:
                return number

    if isinstance(value, int) and not isinstance(value, bool):
        if value in VEHICLE_TYPES:
            return value

    raise ValueError("Vehicle type must be Car, Bus, or Bike.")


def positive_id(value):
    if isinstance(value, bool):
        raise ValueError("Vehicle ID must be a positive integer.")

    try:
        vehicle_id = int(value)
    except (TypeError, ValueError):
        raise ValueError("Vehicle ID must be a positive integer.")

    if vehicle_id <= 0:
        raise ValueError("Vehicle ID must be a positive integer.")

    return vehicle_id


def add_state(result):
    try:
        result["state"] = get_state()
    except Exception as exc:
        result["stateError"] = str(exc)

    return result


class TrafficFlowHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def log_message(self, format_string, *args):
        print(
            "[TrafficFlow] " + format_string % args,
            flush=True
        )

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/status":
            try:
                send_json(self, get_state())
            except Exception as exc:
                send_json(
                    self,
                    {"ok": False, "error": str(exc)},
                    500
                )
            return

        if path == "/":
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 1000000:
                send_json(
                    self,
                    {"ok": False, "error": "Invalid request body."},
                    400
                )
                return

            data = json.loads(
                self.rfile.read(length).decode("utf-8")
            )

            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")

            if path == "/api/add":
                result = self.handle_add(data)

            elif path == "/api/signal":
                result = self.handle_signal(data)

            elif path == "/api/automatic":
                result = send_to_engine("AUTO")
                result = add_state(result)

            elif path == "/api/search":
                result = self.handle_search(data)

            else:
                send_json(
                    self,
                    {"ok": False, "error": "API endpoint not found."},
                    404
                )
                return

            send_json(self, result)

        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            send_json(
                self,
                {"ok": False, "error": str(exc)},
                400
            )

        except Exception as exc:
            print(f"[TrafficFlow] Request error: {exc}", flush=True)
            send_json(
                self,
                {"ok": False, "error": str(exc)},
                500
            )

    def handle_add(self, data):
        lane = normalize_lane(data.get("lane"))
        vehicle_id = positive_id(data.get("id"))
        vehicle_type = normalize_vehicle_type(data.get("type"))

        result = send_to_engine(
            f"ADD {lane} {vehicle_id} {vehicle_type}"
        )

        return add_state(result)

    def handle_signal(self, data):
        lane = normalize_lane(data.get("lane"))

        result = send_to_engine(f"SIGNAL {lane}")

        return add_state(result)

    def handle_search(self, data):
        vehicle_id = positive_id(data.get("id"))
        result = send_to_engine(f"SEARCH {vehicle_id}")

        vehicle = result.get("vehicle")

        if vehicle:
            result["vehicleLane"] = vehicle.get("lane")
            result["lane"] = vehicle.get("lane")

        return add_state(result)


def main():
    try:
        start_engine()

        server = ThreadingHTTPServer(
            (HOST, PORT),
            TrafficFlowHandler
        )

        print(
            f"TrafficFlow server running on port {PORT}",
            flush=True
        )

        server.serve_forever()

    except KeyboardInterrupt:
        print("\nTrafficFlow server stopping...", flush=True)

    except Exception as exc:
        print(f"Startup error: {exc}", file=sys.stderr, flush=True)
        raise

    finally:
        if engine is not None and engine.poll() is None:
            engine.terminate()

            try:
                engine.wait(timeout=5)
            except subprocess.TimeoutExpired:
                engine.kill()
                engine.wait()


if __name__ == "__main__":
    main()
