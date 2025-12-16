import socket
import threading
from queue import Empty, Queue
from typing import Optional

from protocol import Message, encode, try_decode_line

# =============================
# Network client
# =============================


class TcpLineClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

        self._sock: Optional[socket.socket] = None
        self._rx_thread: Optional[threading.Thread] = None
        self.running = threading.Event()

        self.inbox: "Queue[Message]" = Queue()
        self.errors: "Queue[str]" = Queue()

    @property
    def connected(self) -> bool:
        return self._sock is not None and self.running.is_set()

    def connect(self) -> None:
        if self.connected:
            return

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((self.host, self.port))
        s.settimeout(0.2)

        self._sock = s
        self.running.set()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

    def close(self) -> None:
        self.running.clear()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None

    def send(self, type_desc: str, *params: str) -> None:
        if not self.connected or self._sock is None:
            raise RuntimeError("Not connected")
        try:
            self._sock.sendall(encode(type_desc, *params))
        except Exception as e:
            self.errors.put(f"Send failed: {e}")
            self.close()

    def _rx_loop(self) -> None:
        assert self._sock is not None
        buf = ""
        while self.running.is_set():
            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    self.errors.put("Disconnected by server.")
                    break

                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    try:
                        msg = try_decode_line(line)
                    except Exception as e:
                        self.errors.put(str(e))
                        self.close()
                        return

                    if msg is None:
                        self.errors.put(f"Malformed line: {line!r}")
                        continue

                    self.inbox.put(msg)

            except socket.timeout:
                continue
            except Exception as e:
                self.errors.put(f"Receive failed: {e}")
                break

        self.running.clear()
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
