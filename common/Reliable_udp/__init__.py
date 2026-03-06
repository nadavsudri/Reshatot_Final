import json
import random
import socket
import time

### this is the ReliableUDP module
### wraps a raw UDP socket and provides reliable send/recv
### implementing - acks, retransmission, window size (dynamic or static)
### 3 way handshake and persistent connection.

##enjoy!

class ReliableUDP:
    def __init__(self, sock:socket.socket, window_size=4, max_msg_size=1024, timeout=2, dynamic_message_size=False):
        self.sock = sock
        self.config = {
            "window_size": window_size,
            "maximum_msg_size": max_msg_size,
            "dynamic_message_size": dynamic_message_size
        }
        self.timeout = timeout
        self._recv_buffer = b""
        self._time_since_change = 0

    ## start of connection (3way handshake) - initiator side
    def connect(self, ip, port):
        self.sock.connect((ip, port))
        ## send SIN message
        self.sock.send("SIN".encode())
        ##recive SIN/ACK
        data = self.sock.recv(1024).decode()
        if data == "SIN/ACK":
            self.sock.send("ACK".encode())
        ## send config to the other side
        self.sock.send(json.dumps(self.config).encode())

    ## start of connection (3way handshake) - listener side
    def accept(self):
        ## get first datagram to know who is connecting
        data, addr = self.sock.recvfrom(1024)
        self.sock.connect(addr)
        if data.decode() == "SIN":
            self.sock.send("SIN/ACK".encode())
            data = self.sock.recv(1024).decode()
            if data == "ACK":
                pass
        ## recive config from the connecting side
        config_data = self.sock.recv(1024).decode()
        self.config = json.loads(config_data)

    ## finish communication (FIN/ACK) - active close
    def close(self):
        self.sock.send("FIN".encode())
        response = self.sock.recv(1024)
        if response:
            response = response.decode()
            if response == "ACK":
                return True
        return False

    ## finish communication (FIN/ACK) - passive close
    def handle_close(self):
        get_fin = self.sock.recv(1024).decode()
        if get_fin == "FIN":
            self.sock.send("ACK".encode())
            return True
        return False

    ##this method is the main implementation of the reliable data transform mechanism
    ##as studied in RESHATOT TIKSHORET course.
    def send(self, source:str):
        #don't do anything if no data was sent
        if not source:
            return

        ## extracting config data from the config dictionary
        max_len = self.config["maximum_msg_size"]
        window_size = self.config["window_size"]

        #encode the data
        encoded_data = source.encode("utf-8")
        #initiallize parameters for the function
        last_sent = 0
        last_ack = 0
        bytes_sent = 0
        ## setting the timout of the socket to NOT be stuck in an endless reading
        self.sock.settimeout(0.1)
        new_size = False
        pending_size = None
        window=[]
        timer = time.time()

        #the main loop of the method
        while True:
            #send the unsent packets in the window
            first = True
            while last_sent-last_ack < window_size:
                if new_size:
                    break
                ##if the given size is new -> don't send new messages
                if bytes_sent >= len(encoded_data):
                    break
                ## if the message sent is the first one after a message size has been changed,
                ## the idea is to stop the stream until the window is fully sent
                if first:
                    timer = time.monotonic()
                    first = False
                ## use chunking and "buffer" to separate the data
                chunk = encoded_data[bytes_sent : bytes_sent + max_len]
                ##send the data with a flag saying the segment is the last one
                ## adding the headres to the packet
                if bytes_sent+len(chunk) ==len(encoded_data):
                    to_send =  self._add_headers(chunk, last_sent, True)
                else:
                    to_send = self._add_headers(chunk, last_sent, False)

                ## appending the sent message to a window
                window.append(to_send)
                ## sending the message via the socket
                self.sock.send(to_send + b"\n")
                ### proccess the ack
                time.sleep(0.001)
                print("sent: ", to_send)
                #updating the total bytes_sent
                bytes_sent += len(chunk)
                last_sent += 1

            while True:
                #get the responses
                res = self._recv_json()
                if res is None:
                    break
                ## skip data packets that arrived while we are still sending
                if "ack" not in res:
                    continue
                ack = res["ack"]
                print("got Ack: ", ack)

                if res["dynamic_message_size"]:
                    dynamic = res["dynamic_message_size"]
                    if max_len != res["message_size"]:
                        new_size = True
                        # saving the new size for when the window is empty
                        pending_size = res["message_size"]

                # if the received ack is bigger than the last acked packet -> move the window
                if ack + 1 > last_ack:
                    last_ack = ack + 1
                    window = [pkt for pkt in window if json.loads(pkt.decode())["seq"] >= last_ack]
                    timer = time.monotonic()

            ### if the message sent completly -> return
            if bytes_sent == len(encoded_data) and last_ack == last_sent:
                self.sock.settimeout(None)
                return

            ##if the new size flag is true (new size has been asked for)
            ##and the window is empty, change the sizeing and set the flags to false.
            if new_size and last_ack == last_sent:
                max_len = pending_size
                new_size = False
                pending_size = None
                continue

            ## if you haven't received a moving window ack till timeout -> resend the window
            ## after the retransmitting, the clock is set to 0 again
            if time.monotonic() - timer > self.timeout:
                print("Timeout...")
                for unacked in window:
                    self.sock.send(unacked + b"\n")
                timer = time.monotonic()

    #reciving message
    def recv(self) -> str:
        ##for testing
        lose_packet = True

        ##init buffers and variabels
        buffer = b""
        message = ""
        expected_seq=0
        last_seq = 0
        dynamic = self.config["dynamic_message_size"]
        ##loose packet number:
        lost_packet = random.randint(0,12)
        lost = False

        while True:
            ##buffering the response
            buffer += self.sock.recv(4096)
            if dynamic and self._do_i_need_to_change_size(self.config["window_size"]):
                self.config["dynamic_message_size"] = True
            else:
                self.config["dynamic_message_size"] = False

            ## JSON sequences seperated by \n
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                data = json.loads(line.decode())

                ## skip ack packets that arrived while we are still receiving
                if "message" not in data:
                    continue

                ## extracting the data
                msg = data["message"]
                seq = data["seq"]
                is_last = data["is_last"]

                ##if the packet number is the one that we want to "loose"
                ##send ack for the prev package
                ##let the sender manage the loss
                if seq == lost_packet and not lost and lose_packet:
                    self._send_ack(expected_seq-1, self.config["dynamic_message_size"])
                    lost = True
                    continue

                ## if the ack we received is the next in sequence (or more)
                elif seq==expected_seq:
                    expected_seq +=1
                    self._send_ack(seq, self.config["dynamic_message_size"])
                    message += msg
                ## send last received ack
                else:
                    self._send_ack(expected_seq-1, self.config["dynamic_message_size"])

                ## if the message is the last one in sequence
                ## makes sure that the method will run until the last message is acked
                if is_last:
                    last_seq = seq
                if is_last and last_seq ==expected_seq-1:
                    return message

    ##add the headers attached in "m"
    ## format into a string representing a JSON object
    def _add_headers(self, source:bytes, m, is_last:bool):
        """
        add the headers to a given string
        :param source:
        :param m:
        :param is_last:
        :return: bytes
        """""
        msg_with_headers = {"message":source.decode(errors="replace"),"seq":m,"is_last":is_last}
        return json.dumps(msg_with_headers).encode("utf-8")

    #sending ack for a given sequence
    def _send_ack(self, ack:int, dynamic:bool = False):
        if dynamic:
            ack_msg = json.dumps({"ack":ack,"dynamic_message_size":True,"message_size":random.randint(3,10)})
        else:
            ack_msg = json.dumps({"ack":ack,"dynamic_message_size":False})
        self.sock.send(ack_msg.encode()+b"\n")

    ### this method recives the socket and recives using recv a JSON object
    ### collected using chunking
    def _recv_json(self):
        try:
            while b"\n" not in self._recv_buffer:
                chunk = self.sock.recv(4096)
                if not chunk:
                    return None
                self._recv_buffer += chunk
        except socket.timeout:
            return None
        line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
        return json.loads(line.decode())

    ## mimics the decision whether to increase or decrease msg size based on the conjection
    def _do_i_need_to_change_size(self, windowsize:int)-> bool:
        change_rate = 3*windowsize
        if self._time_since_change>=change_rate:
            self._time_since_change = 0
            return True
        else:
            print("time. to change size", self._time_since_change)
            self._time_since_change += 1
            return False
