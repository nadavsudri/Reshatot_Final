import json
import socket,json
import random
import time

###  server constants  ####
change_rate=None
time_since_change = 0

## mimics the servers decision whether to increase or decrease msg size based on the conjection
def do_i_need_to_change_size(windowsize:int)-> bool:
    global change_rate
    global time_since_change
    change_rate = 3*windowsize
    if time_since_change>=change_rate:
        time_since_change = 0
        return True
    else:
        print("time. to change size", time_since_change)
        time_since_change += 1
        return False

## connecting a socket to given ip and port
def listener_connection(ip, port)->socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((ip, port))
    sock.listen()
    return sock

### Receiving the first confing request
def receive_config_request(client_socket):
    ## get the request from the socket
    # convert it to JSON
    config_request = client_socket.recv(1024).decode()
    config_request = json.loads(config_request)
    ## distinguish the types of request (from text or file)
    if config_request["type"] == "F" or config_request["type"] == "f":
        # if passed using a file
        response = open_file_json(input("Please enter the file path: "))
        client_socket.send(response.encode())
        response = json.loads(response)
        if isinstance(response, str):
            return json.loads(response)
        else:
            return response
    if config_request["type"] == "T" or config_request["type"] == "t":

        ## requesting from user for parameters
        message_file = ""
        msg_size = input("Please enter the message size: ")
        window_size = input("Please enter the window size: ")
        dynamic_msg_size = input("Please enter the dynamic message size [T/F]: ")
        dynamic_msg_size = True if dynamic_msg_size == "T" or dynamic_msg_size=="t" else False

        ## assembling the dictionary response
        conf = {"message": message_file, "maximum_msg_size":int(msg_size), "window_size": int(window_size),
                "dynamic_message_size": dynamic_msg_size}
        ## send response JSON
        client_socket.send(json.dumps(conf).encode())
        return conf
    return None

def random_size():
    return random.randint(3,10)

## opening a file containing JSON format
def open_file_json(file:str):
    with open(file) as f:
        data=  f.read()
        return json.dumps(data)

#sending ack for a given sequence
def send_ack(socket:socket.socket,ack:int,dynamic:bool = False):
    if dynamic:
        ack_msg = json.dumps({"ack":ack,"dynamic_message_size":True,"message_size":random_size()})
    else:
        ack_msg = json.dumps({"ack":ack,"dynamic_message_size":False})
    socket.send(ack_msg.encode()+b"\n")

#reciving message
def recv_msg(socket:socket.socket,config):
    ##for testing
    lose_packet = True

    ##init buffers and variabels
    buffer = b""
    message = ""
    expected_seq=0
    last_seq = 0
    dynamic = config["dynamic_message_size"]
    ##loose packet number:
    lost_packet = random.randint(0,12)
    lost = False
    while True:
        ##buffering the response
        buffer += socket.recv(4096)
        if dynamic and do_i_need_to_change_size(config["window_size"]):
            config["dynamic_message_size"] = True
        else:
            config["dynamic_message_size"] = False

        ## JSON sequences seperated by \n
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            data = json.loads(line.decode())

            ## extracting the data
            msg = data["message"]

            seq = data["seq"]
            is_last = data["is_last"]

            ##if the packet number is the one that we want to "loose"
            ##send ack for the prev package
            ##let the client manage the loss
            if seq == 4 and not lost and lose_packet:
                send_ack(socket, expected_seq-1, config["dynamic_message_size"])

                lost = True
                continue

            ## if the ack we received is the next in sequence (or more)
            elif seq==expected_seq:
                expected_seq +=1
                send_ack(socket, seq, config["dynamic_message_size"])

                message += msg
            ## send last received ack
            else:
                send_ack(socket, expected_seq-1, config["dynamic_message_size"])
            ## if the message is the last one in sequence
            ## makes sure that the method will run until the last message is acked
            if is_last:
                last_seq = seq
            if is_last and last_seq ==expected_seq-1:

                return message

def main():

    # accept connection via 3 way handshake
    listener_sock = listener_connection("127.0.0.1", 5555)
    #open and accept socket
    client_socket, client_address = listener_sock.accept()
    print("Client connected", client_address)
    #Atemppting to make 3-way handshake
    is_connected = False
    while not is_connected:
        data = client_socket.recv(1024).decode()
        if data =="SIN":
            client_socket.send("SIN/ACK".encode())
            data = client_socket.recv(1024).decode()
            if data == "ACK":
                is_connected = True
                break
        print("Connection failed, Retrying...")
    config =receive_config_request(client_socket)
    #printing when connected
    print("Connected", is_connected)

    #loop as long connection is established
    while is_connected:
        data = recv_msg(client_socket,config)
        if not data:
                continue
        # if data =="WIN_SIZE":
                # response(client_socket,)#incomplete!!
        print("Server Received: ", data)
        get_fin = client_socket.recv(1024).decode()
        if get_fin=="FIN":
            client_socket.send("ACK".encode())
        else:
            pass

main()