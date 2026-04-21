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
    def recv(self) -> bytes:
        raise NotImplementedError
    def close(self):
        raise NotImplementedError
    def flush(self):
        raise NotImplementedError


class TCPTransport(Transport):
    """Wraps a plain TCP socket."""
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._recv_buffer = b""

    def send(self, data: str):
        if isinstance(data,str):
            data = data.encode()
        self.sock.sendall(data)

    def recv(self) -> bytes:
      # Return buffered leftover data first
      if self._recv_buffer:
          data = self._recv_buffer
          self._recv_buffer = b""
          return data
      data = self.sock.recv(65535)
      if isinstance(data,str):
          data = data.decode()
      return data


    def close(self):
        self.sock.close()

    def buffer_leftover(self, data: bytes):
        """Store leftover data for next recv() call"""
        self._recv_buffer = data + self._recv_buffer

    #empty the socket
    def flush(self):
        self._recv_buffer=b""
        print("flushed")
        original_timeout = self.sock.gettimeout()
        try:
            self.sock.setblocking(False)
            while True:
                try:
                    self.sock.recv(4096)
                except(BlockingIOError):
                    break       
        except (OSError):
            pass
        finally:
            self.sock.setblocking(True)
            self.sock.settimeout(original_timeout)


class RUDPTransport(Transport):
    """Wraps a ReliableUDP instance."""
    def __init__(self, rudp: ReliableUDP):
        self.rudp = rudp

    def send(self, data: str):
    

        if isinstance(data, str):
            data = data.encode()    
        self.rudp.send(data)

    def recv(self) -> str:
        return self.rudp.recv()

    def close(self):
        self.rudp.close()
    def accept(self):
        self.rudp.accept()
    def flush(self):
        """Reset RUDP state between persistent requests"""
        if hasattr(self, 'rudp'):
            self.rudp.reset_sequence()