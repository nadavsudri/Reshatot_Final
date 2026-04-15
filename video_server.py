
import socket, threading
from transport import Transport, TCPTransport, RUDPTransport
from Reliable_udp import ReliableUDP
import cv2
import struct
import math

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

FRAMES_PER_CHUNK = 30

def get_chunk(video_name, quality_level, start_frame):
    cap = cv2.VideoCapture(video_name)
    if not cap.isOpened():
        print(f"[-] Couldn't open video {video_name}")
        return None
    
    chunk_data = b''
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    for _ in range(FRAMES_PER_CHUNK):
        success, img = cap.read()
        if not success:
            break  # end of video
        
        # resize for quality
        if quality_level == "Medium":
            img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
        elif quality_level == "Low":
            img = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
        
        # encode frame as JPEG
        _, encoded = cv2.imencode('.jpg', img)
        frame_bytes = encoded.tobytes()
        
        # prefix each frame with its size so client knows where it ends
        frame_size = struct.pack('!I', len(frame_bytes))
        chunk_data += frame_size + frame_bytes
    
    cap.release()
    return chunk_data

def parse_request(request: str) -> tuple:
    # GET /balls.mp4/High/0 HTTP/1.1 -> (balls.mp4, High, 0)
    first_line = request.split('\r\n')[0]
    path = first_line.split(' ')[1]        #
    parts = path.strip('/').split('/')     
    
    video_name  = parts[0]
    quality     = parts[1]
    start_frame = int(parts[2])
    
    return video_name, quality, start_frame

# handling client requests 
def handle_client(conn: Transport):
    while True:
        request = conn.recv()
        if not request:
            break
        
        video_name, quality, start_frame = parse_request(request)
        chunk_data = get_chunk(video_name, quality, start_frame)
        
        if chunk_data is None:
            conn.send("HTTP/1.1 404 Not Found\r\n\r\n")
            break
        
        response  = "HTTP/1.1 200 OK\r\n"
        response += f"Content-Length: {len(chunk_data)}\r\n"
        response += "\r\n"
        
        conn.send(response.encode() + chunk_data)
    
    conn.close()

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

    udp_thread.join()
    tcp_thread.join()

if __name__ == "__main__":
    main()