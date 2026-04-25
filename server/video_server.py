import socket, threading
from transport import Transport, TCPTransport, RUDPTransport
from datetime import datetime
from Reliable_udp import ReliableUDP
import cv2
import struct
import math
import time
import base64

debug = False
showoff = False

##debugging section##
def timestamp():
    return datetime.now().strftime("[%d/%m/%y | %H:%M:%S]")
def debug_out(data:str,e = None):
    exep = "With Exeption "+e if e else ""
    if debug:
        print(f"{timestamp()} : {data} {exep}")

#ping 8.8.8.8
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"
    

def register_to_dns(my_ip):
    try:
        register_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Give the operation system permission to broadcast
        register_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # building the signing massege to DNS server
        register_msg = f"REGISTER video.server.local {my_ip}"
        
        # Broadcasting throw port 53
        register_sock.sendto(register_msg.encode('ascii'), ('255.255.255.255', 53))
        register_sock.close()
        print(f"[*] Successfully broadcasted registration to DNS: {register_msg}")
    except Exception as e:
        print(f"[-] Failed to register to DNS: {e}")


# Keep the VideoCapture object open globally or in a class for speed
video_cache = {}
def get_chunk(video_name, quality:str, frame_num):

    if video_name not in video_cache:
        video_path = f"library/{video_name}"
        video = cv2.VideoCapture(video_path)
        video_cache[video_name] = video
        debug_out("Cashing video")
    else:
        video = video_cache[video_name]
    # 1. Set the frame position
    video.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    success, frame = video.read()
    if not success:
        return None,0
    # 2. Downscale for "Low" quality to save bandwidth
    if quality.lower() == "high":
        frame = cv2.resize(frame, (1920, 1080))
    elif quality.lower() == "medium":
        frame = cv2.resize(frame, (640, 480))
    elif quality.lower()== "low":
        frame = cv2.resize(frame, (256, 144))
    
        
    debug_out(f"Frame is {len(frame)} bytes [{quality}]")
    # 3. Encode to JPEG (in memory, no temp files!)
    # Higher quality number = better image but more bytes
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
    success, buffer = cv2.imencode('.jpg', frame, encode_param)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    debug_out(f"[DEBUG] Total frames: {total_frames}, requested: {frame_num}")
    
    if not success:
        return None,0
    # 4. Convert to Base64 so it can be sent as "text" in your HTTP-like response
    return base64.b64encode(buffer).decode('utf-8'),total_frames

def parse_request(request: bytes) -> tuple:
    # GET /balls.mp4/High/0 HTTP/1.1 -> (balls.mp4, High, 0)
    debug_out(request)
    first_line = request if isinstance(request,str) else request.decode('utf-8').split('\r\n')[0]
    path = first_line.split(' ')[1]        #
    parts = path.strip('/').split('/')     
    video_name  = parts[0]
    quality     = parts[1]
    start_frame = int(parts[2])
    debug_out(f"Server received request for: {video_name} {quality} {start_frame}")
    
    return video_name, quality, start_frame

# handling client requests 
def handle_client(conn: Transport):
    frame_count = 0
    print("[*] Client connected")
    #receving data from socket, encodes it [if no data arrive - continue]
    while True:
        request = conn.recv()
        if isinstance(request,str):
            request = request.encode()
        if not request:
            continue
        if b"<DISCONNECT>" in request:
            conn.close()
            print("[X] Client disconnected")
            return
        #getting and unpacking request, and getting the chunk
        video_name, quality, start_frame = parse_request(request)
        chunk_data,frame= get_chunk(video_name, quality, start_frame)
        #if no data was found - return 404
        if chunk_data is None:
            conn.send("HTTP/1.1 404 Not Found\r\n\r\n"+"<END_OF_CHUNK>")
            continue
        #built return packet - header + content length + data
        response  = "HTTP/1.1 200 OK\r\n"
        response += f"Content-Length: {len(chunk_data)}\r\n"
        response += "\r\n"
        #marking end of chunk / streamq
        frame_count+=1
        if frame_count == frame:
            full_response = response.encode() + chunk_data.encode() + b"<END_OF_STREAM>"
        else:
            full_response = response.encode() + chunk_data.encode() + b"<END_OF_CHUNK>"
        
        conn.send(full_response)
        # time.sleep(0.5)
        

def run_rudp_server(sock):
    while True:
        rudp = ReliableUDP(sock)
        rudp.accept()
        conn = RUDPTransport(rudp)
        t = threading.Thread(target=handle_client, args=(conn,))
        t.start()
 
def run_tcp_server(sock):
    while True:
        client_sock, addr = sock.accept()
        conn = TCPTransport(client_sock)
        t = threading.Thread(target=handle_client, args=(conn,))
        t.start()

def main():
    my_ip = get_local_ip()
    print(f"[*] Video Server starting up. My IP is: {my_ip}")

    # register to DNS
    register_to_dns(my_ip)

    # UDP socket for RUDP on port 8080
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(('0.0.0.0', 8080))
    print("[*] RUDP listener up on port 8080")

    # TCP socket for HTTP on port 80
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind(('0.0.0.0', 80))
    tcp_socket.listen(5)
    print("[*] HTTP listener up on port 80")

    # start both listeners in separate threads
    udp_thread = threading.Thread(target=run_rudp_server, args=(udp_socket,))
    tcp_thread = threading.Thread(target=run_tcp_server, args=(tcp_socket,))

    udp_thread.start()
    tcp_thread.start()

    # udp_thread.join()
    # tcp_thread.join()

if __name__ == "__main__":
    main()