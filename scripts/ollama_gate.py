"""The gate in front of the local Ollama, so the shared console can ask it questions through a tunnel (issue 17).

    python scripts/ollama_gate.py        # listens on 127.0.0.1:GATE_PORT; the tunnel (Tailscale Funnel) points here

Ollama itself has no password, and its API can also pull, create and delete models. The tunnel exposes only this gate,
which lets through two requests and nothing else: GET /api/version (is the model there?) and POST /api/chat for
MODEL only. Each needs "Authorization: Bearer <key>", the key being OLLAMA_GATE_KEY from the environment or the
git-ignored .env. One question at a time; another one meanwhile gets 429. Settings: evidence/assistant_settings.py.
"""
import hmac
import http.client
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.assistant_settings import (ANSWER_SECONDS, GATE_IDLE_SECONDS, GATE_KEY_NAME, GATE_MAX_BODY,
                                         GATE_MAX_CONNECTIONS, GATE_PORT, MODEL, OLLAMA_URL, ROOT)


def gate_key():
    """The key from the environment, else from the git-ignored .env; empty when neither has it."""
    if os.environ.get(GATE_KEY_NAME):
        return os.environ[GATE_KEY_NAME].strip()
    env = ROOT / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
        name, _, value = line.partition("=")
        if name.strip() == GATE_KEY_NAME:
            return value.strip().strip('"').strip("'")
    return ""


def handler(key, upstream=OLLAMA_URL, model=MODEL):
    """The request handler class for a gate with this key, forwarding to `upstream`."""
    busy = threading.Semaphore(1)
    target = urlsplit(upstream)

    class Gate(BaseHTTPRequestHandler):
        timeout = GATE_IDLE_SECONDS   # a silent connection is dropped, so it cannot hold a thread for ever

        def log_message(self, *_):   # no request lines in the terminal: they would carry nothing useful
            pass

        def _refuse(self, status, words):
            body = json.dumps({"error": words}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _allowed(self):
            given = self.headers.get("Authorization", "")
            return bool(key) and hmac.compare_digest(given.encode(), f"Bearer {key}".encode())

        def _forward(self, method, body=None):
            connection = http.client.HTTPConnection(target.hostname, target.port, timeout=ANSWER_SECONDS)
            started = False   # once the answer has begun, a failure can only end it, not send a second reply
            try:
                connection.request(method, self.path, body=body, headers={"Content-Type": "application/json"})
                reply = connection.getresponse()
                started = True
                self.send_response(reply.status)
                self.send_header("Content-Type", reply.getheader("Content-Type", "application/json"))
                self.end_headers()
                while piece := reply.read1(65536):   # pass the answer on as the model writes it
                    self.wfile.write(piece)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass   # the console stopped listening (the reader left); nothing more to send
            except OSError:
                if not started:
                    self._refuse(502, "The model on this computer did not answer.")
            finally:
                connection.close()

        def do_GET(self):
            if not self._allowed():
                return self._refuse(401, "Not allowed.")
            if self.path != "/api/version":
                return self._refuse(404, "Not here.")
            self._forward("GET")

        def do_POST(self):
            if not self._allowed():
                return self._refuse(401, "Not allowed.")
            if self.path != "/api/chat":
                return self._refuse(404, "Not here.")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._refuse(400, "Not a question this gate understands.")
            if not 0 < length <= GATE_MAX_BODY:
                return self._refuse(413, "The question is empty or too large.")
            body = self.rfile.read(length)
            try:
                asked = json.loads(body).get("model")
            except (ValueError, AttributeError):
                return self._refuse(400, "Not a question this gate understands.")
            if asked != model:
                return self._refuse(403, f"Only {model} may be asked here.")
            if not busy.acquire(blocking=False):
                return self._refuse(429, "The model is answering someone else. Try again in a minute.")
            try:
                self._forward("POST", body)
            finally:
                busy.release()

    return Gate


class Server(ThreadingHTTPServer):
    """A threading server that holds at most GATE_MAX_CONNECTIONS connections; one more is closed straight away."""
    daemon_threads = True

    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(GATE_MAX_CONNECTIONS)
        super().__init__(*args)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main():
    key = gate_key()
    if len(key) < 32:
        sys.exit(f"Set {GATE_KEY_NAME} in .env to a long random value first, for example: openssl rand -hex 32")
    print(f"Gate on http://127.0.0.1:{GATE_PORT}, passing questions for {MODEL} to {OLLAMA_URL}. Ctrl-C stops it.")
    Server(("127.0.0.1", GATE_PORT), handler(key)).serve_forever()


if __name__ == "__main__":
    main()
