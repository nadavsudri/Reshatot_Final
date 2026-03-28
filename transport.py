import socket
import sys
import os

#this code is a wrapper for a tcp \ udp sockets to act the same - reduce code.

sys.path.append(os.path.join(os.path.dirname(__file__), 'common'))
from Reliable_udp import ReliableUDP


class Transport:
    """Base wrapper — defines the interface both protocols must implement."""
    def send(self, data: str):
        raise NotImplementedError
    def recv(self) -> str:
        raise NotImplementedError
    def close(self):
        raise NotImplementedError


class TCPTransport(Transport):
    """Wraps a plain TCP socket."""
    def __init__(self, sock: socket.socket):
        self.sock = sock

    def send(self, data: str):
        self.sock.sendall(data.encode())

    def recv(self) -> str:
        return self.sock.recv(65535).decode()

    def close(self):
        self.sock.close()


class RUDPTransport(Transport):
    """Wraps a ReliableUDP instance."""
    def __init__(self, rudp: ReliableUDP):
        self.rudp = rudp

    def send(self, data: str):
        self.rudp.send(data)

    def recv(self) -> str:
        return self.rudp.recv()

    def close(self):
        self.rudp.close()