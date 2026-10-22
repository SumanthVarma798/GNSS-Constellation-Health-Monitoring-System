"""The gate in front of the local Ollama (scripts/ollama_gate.py): only questions for one model, only with the key."""
import http.client
import json
import socket
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ollama_gate  # noqa: E402

KEY, MODEL = "k" * 40, "qwen3:8b"
LET_GO, HOLDING = threading.Event(), threading.Event()   # the stand-in waits for LET_GO; HOLDING: it has a question


class Ollama(BaseHTTPRequestHandler):
    """Stands in for Ollama: a version, and a chat answer in two pieces once LET_GO is set."""
    def log_message(self, *_):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"version": "test"}')

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        HOLDING.set()
        LET_GO.wait(5)
        self.send_response(200)
        self.end_headers()
        for piece in ("It is ", "CelesTrak."):
            self.wfile.write(json.dumps({"message": {"content": piece}}).encode() + b"\n")


def serve(handler_class, server_class=ThreadingHTTPServer):
    server = server_class(("127.0.0.1", 0), handler_class)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def gate():
    LET_GO.set()
    ollama = serve(Ollama)
    front = serve(ollama_gate.handler(KEY, upstream=f"http://127.0.0.1:{ollama.server_port}", model=MODEL),
                  ollama_gate.Server)
    yield f"http://127.0.0.1:{front.server_port}"
    front.shutdown()
    ollama.shutdown()


def ask(gate, path="/api/chat", key=KEY, model=MODEL, method="POST"):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return requests.request(method, gate + path, headers=headers, timeout=10,
                            json={"model": model, "messages": []} if method == "POST" else None)


def test_a_question_with_the_key_reaches_the_model_and_comes_back_whole(gate):
    reply = ask(gate)
    assert reply.status_code == 200
    assert "".join(json.loads(line)["message"]["content"] for line in reply.text.splitlines()) == "It is CelesTrak."
    assert ask(gate, "/api/version", method="GET").json() == {"version": "test"}


@pytest.mark.parametrize("key", ["", "wrong", KEY[:-1]])
def test_without_the_right_key_nothing_passes(gate, key):
    assert ask(gate, key=key).status_code == 401
    assert ask(gate, "/api/version", key=key, method="GET").status_code == 401


@pytest.mark.parametrize("path, method", [("/api/pull", "POST"), ("/api/delete", "POST"), ("/api/tags", "GET")])
def test_only_chat_and_version_pass_even_with_the_key(gate, path, method):
    assert ask(gate, path, method=method).status_code == 404


def test_only_the_one_model_may_be_asked(gate):
    assert ask(gate, model="llama3:70b").status_code == 403


def test_a_second_question_while_one_is_answered_is_turned_away(gate):
    LET_GO.clear()
    HOLDING.clear()
    first = threading.Thread(target=ask, args=(gate,))
    first.start()
    try:
        assert HOLDING.wait(5)   # the first question has reached the model and holds it
        assert ask(gate).status_code == 429
    finally:
        LET_GO.set()
        first.join()


def test_the_gate_will_not_start_without_a_long_key(monkeypatch):
    monkeypatch.setenv(ollama_gate.GATE_KEY_NAME, "short")
    with pytest.raises(SystemExit, match="openssl rand"):
        ollama_gate.main()


def test_a_size_that_is_not_a_number_is_refused_not_crashed_on(gate):
    port = int(gate.rsplit(":", 1)[1])
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.putrequest("POST", "/api/chat")
    connection.putheader("Authorization", f"Bearer {KEY}")
    connection.putheader("Content-Length", "abc")
    connection.endheaders()
    assert connection.getresponse().status == 400


def test_silent_connections_are_dropped_and_cannot_pile_up(monkeypatch):
    monkeypatch.setattr(ollama_gate, "GATE_MAX_CONNECTIONS", 2)
    monkeypatch.setattr(ollama_gate, "GATE_IDLE_SECONDS", 1)
    front = serve(ollama_gate.handler(KEY, upstream="http://127.0.0.1:9"), ollama_gate.Server)
    address = ("127.0.0.1", front.server_port)
    try:
        silent = [socket.create_connection(address) for _ in range(2)]   # they hold both places, saying nothing
        time.sleep(0.2)
        with pytest.raises(requests.ConnectionError):   # a third is closed at once
            requests.get(f"http://127.0.0.1:{front.server_port}/api/version", timeout=3)
        for quiet in silent:   # after the idle limit the gate has hung up on each
            quiet.settimeout(5)
            assert quiet.recv(1) == b""
        time.sleep(0.2)
        assert requests.get(f"http://127.0.0.1:{front.server_port}/api/version", timeout=3).status_code == 401
    finally:
        front.shutdown()
