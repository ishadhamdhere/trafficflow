
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

LANES = {"North", "South", "East", "West"}
VEHICLE_TYPES = {"Car": 1, "Bus": 2, "Bike": 3}

engine = None
engine_lock = threading.Lock()


def start_engine():
    """Start the persistent C traffic engine."""
    global engine

    if os.name == "nt":
        executable = BASE_DIR / "main.exe"
    else:
        executable = BASE_DIR / "main"

    if not executable.is_file():
        raise FileNotFoundError(
            f"C engine executable not found: {executable}. "
            "Compile main.c before starting the server."
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
        raise RuntimeError("The C traffic engine exited during startup.")


def send_to_engine(command):
    """Send one command to C and read its JSON response."""
    with engine_lock:
        if engine is None or engine.poll() is not None:
            raise RuntimeError("The C traffic engine is not running.")

        try:
            engine.stdin.write(command + "\n")
            engine.stdin.flush()

            response = engine.stdout.readline()

            if not response:
                raise RuntimeError(
                    "The C engine returned no response. "
                    "Check its server-mode command protocol."
                )

            return json.loads(response)

        except (BrokenPipeError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Could not communicate with the C engine: {exc}"
            ) from exc


def send_json(handler, data, status=200):
    body = json.dumps(data).encode("utf-8")

    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class TrafficFlowHandler(SimpleHTTPRequestHandler):
    """Serve the dashboard and provide the TrafficFlow API."""

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(BASE_DIR),
            **kwargs
        )

    def log_message(self, format_string, *args):
        print(
            f"[TrafficFlow] {self.address_string()} - "
            + format_string % args,
            flush=True
        )

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/status":
            self.handle_status()
            return

        if path == "/":
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 1_000_000:
                send_json(
                    self,
                    {"success": False, "error": "Invalid request body."},
                    400
                )
                return

            raw_body = self.rfile.read(length)
            data = json.loads(raw_body.decode("utf-8"))

            if not isinstance(data, dict):
                send_json(
                    self,
                    {"success": False, "error": "Expected a JSON object."},
                    400
                )
                return

            if path == "/api/add":
                self.handle_add(data)

            elif path == "/api/signal":
                self.handle_signal(data)

            elif path == "/api/automatic":
                self.handle_automatic()

            elif path == "/api/search":
                self.handle_search(data)

            else:
                send_json(
                    self,
                    {"success": False, "error": "API endpoint not found."},
                    404
                )

        except json.JSONDecodeError:
            send_json(
                self,
                {"success": False, "error": "Request contains invalid JSON."},
                400
            )

        except (ValueError, TypeError) as exc:
            send_json(
                self,
                {"success": False, "error": str(exc)},
                400
            )

        except Exception as exc:
            print(f"[TrafficFlow] Request error: {exc}", flush=True)
            send_json(
                self,
                {"success": False, "error": str(exc)},
                500
            )

    def handle_status(self):
        try:
            result = send_to_engine("STATUS")
            send_json(self, result)
        except Exception as exc:
            send_json(
                self,
                {"success": False, "error": str(exc)},
                500
            )

    def handle_add(self, data):
        lane = data.get("lane")
        vehicle_id = data.get("id")
        vehicle_type = data.get("type")

        if lane not in LANES:
            raise ValueError(
                "Lane must be North, South, East, or West."
            )

        try:
            vehicle_id = int(vehicle_id)
        except (ValueError, TypeError):
            raise ValueError("Vehicle ID must be an integer.")

        if vehicle_id <= 0:
            raise ValueError("Vehicle ID must be positive.")

        if vehicle_type not in VEHICLE_TYPES:
            raise ValueError("Vehicle type must be Car, Bus, or Bike.")

        command = (
            f"ADD {lane} {vehicle_id} "
            f"{VEHICLE_TYPES[vehicle_type]}"
        )

        result = send_to_engine(command)
        send_json(self, result)

    def handle_signal(self, data):
        lane = data.get("lane")

        if lane not in LANES:
            raise ValueError(
                "Lane must be North, South, East, or West."
            )

        result = send_to_engine(f"SIGNAL {lane}")
        send_json(self, result)

    def handle_automatic(self):
        result = send_to_engine("AUTO")
        send_json(self, result)

    def handle_search(self, data):
        vehicle_id = data.get("id")

        try:
            vehicle_id = int(vehicle_id)
        except (ValueError, TypeError):
            raise ValueError("Vehicle ID must be an integer.")

        if vehicle_id <= 0:
            raise ValueError("Vehicle ID must be positive.")

        result = send_to_engine(f"SEARCH {vehicle_id}")
        send_json(self, result)


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

        if os.environ.get("PORT") is None:
            print(
                f"Open http://127.0.0.1:{PORT} in your browser.",
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
