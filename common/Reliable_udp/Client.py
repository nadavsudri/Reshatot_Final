import json
import socket
import time

### this is the implementation for ASS3 in RESHATOT course
### this code is representing a reliable data stream as learned in the course
### implementing - acks, retransmission, window size (dynamic or static)
### 3 way handshake and presistant connection.
### the code is well documanetd and written in pythonic lingo

##enjoy!

def finish_communication(socket:socket.socket):
    socket.send("FIN".encode())
    response=socket.recv(1024)
    if response:
        response=response.decode()
        if response=="ACK":
            return True
    return False


def open_file_json(file:str):
    with open(file) as f:
        data=  f.read()
        return json.dumps(data)

## start of connection (3way handshake)
def start_connection(socket:socket.socket,port=5555,ip="127.0.0.1"):
    socket.connect((ip, port))
    ## send SIN message
    socket.send("SIN".encode())
    ##recive SIN/ACK
    data_rcv = socket.recv(1024).decode()
    if data_rcv == "SIN/ACK":
        socket.send("ACK".encode())
    return True # return true to verify an establishment.
### this method recives a socket, and reciving using recv a JSON object
### collected using chunking
recv_buffer = b""
def recv_json(sock):
    global recv_buffer
    try:
        while b"\n" not in recv_buffer:
            chunk = sock.recv(4096)
            if not chunk:
                return None
            recv_buffer += chunk
    except socket.timeout:
        return None

    line, recv_buffer = recv_buffer.split(b"\n", 1)
    return json.loads(line.decode())


## send request for window size (only after handshake)
def ask_for_config(socket:socket.socket, source):
    #send the request with source
    request = {"request":"config","type":source}
    socket.send(json.dumps(request).encode())
    data_rcv = socket.recv(1024).decode()
    data_rcv = json.loads(data_rcv)
    ##if the data is wrapped twice
    if isinstance(data_rcv, str):
        data_rcv = json.loads(data_rcv)
    return data_rcv

##add the headers attached in "m"
## format into a string representing a JSON object
def add_headers(source:bytes,m,is_last:bool):
    """
    add the headers to a given string
    :param source: 
    :param m: 
    :param is_last: 
    :return: bytes
    """""
    msg_with_headers = {"message":source.decode(errors="replace"),"seq":m,"is_last":is_last}
    return json.dumps(msg_with_headers).encode("utf-8")

def send_message(sock:socket.socket, source:str, config:dict, timeout:int):
    ##this method is the main implementation of the reliable data transform mechanism
    ##as studied in RESHATOT TIKSHORET course.
    #don't do anything if no data was sent
    if not source:
        return

    ## extracting config data from the config dictionary
    max_len = config["maximum_msg_size"]
    window_size = config["window_size"]

    #encode the data
    encoded_data = source.encode("utf-8")
    #initiallize parameters for the function
    last_sent = 0
    last_ack = 0
    bytes_sent = 0
    ## setting the timout of the socket to NOT be stuck in an endless reading
    sock.settimeout(0.1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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
                to_send =  add_headers(chunk, last_sent, True)
            else:
                to_send = add_headers(chunk, last_sent, False)

            ## appending the sent message to a window
            window.append(to_send)
            ## sending the message via the socket
            sock.send(to_send + b"\n")
            ### proccess the ack
            time.sleep(0.001)
            print("client sent: ", to_send)
            #updating the total bytes_sent
            bytes_sent += len(chunk)
            last_sent += 1
        while True:
            #get the responses
            res = recv_json(sock)
            if res is None:
                break
            ack = res["ack"]
            print("Server sent Ack: ", ack)

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
            return

        #  if the response from the server included the flag, change the msg size


        ##if the new size flag is true (new size has been asked for)
        ##and the window is empty, change the sizeing and set the flags to false.
        if new_size and last_ack == last_sent:
            max_len = pending_size
            new_size = False
            pending_size = None
            continue

        ## if you haven't received a moving window ack till timeout -> resend the window
        ## after the retransmitting, the clock is set to 0 again
        if time.monotonic() - timer > timeout:
            print("Timeout...")
            for unacked in window:
                sock.send(unacked + b"\n")
            timer = time.monotonic()

def main():

    ## opening the socket and starting the connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    start_connection(sock)

    ##letting the user choose if to work with typing or files
    work_type =input("File or Type [F/T] >>>  ")
    if work_type=="t" or work_type=="T":
        timeout = int(input("Timeout (seconds) >>>  "))

    ## ask the server for configuration (negotiation)
    config = ask_for_config(sock, work_type)

    # start sending messages
    while True:
        ## proccess file from user input
        if work_type=="f" or work_type=="F":

            ##detects end of communication
            path = input("Enter file path >>>  ")
            if path =="/exit":
                if finish_communication(sock):
                    print("Connection closed \n")
                    print("socket closed \n")
                    sock.close()
                    break
            file = json.loads(open_file_json())
            if isinstance(file, str):
                file = json.loads(file)
            try:
                read = open(file["message"])
                data = read.read()
            except json.decoder.JSONDecodeError:
                data = file["message"]
            timeout = file["timeout"]
            send_message(sock,data,config,timeout)
        ## not a file -> using input from user as a message
        else:
            data = input(">>> ")
            if data =="/exit":

                if finish_communication(sock):
                    print("Connection closed \n")
                    print("socket closed \n")
                    sock.close()
                    break
                else:
                    print("Connection not closed; Error \n")
            send_message(sock,data,config,timeout)


if __name__ == "__main__":
    main()
