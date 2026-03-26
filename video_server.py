import socket
import cv2
import struct
import math

# Finding the local IP in the net by sending something to google 
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

# define the size of each piece to 4000
CHUNK_SIZE = 4000 
WINDOW_SIZE = 5      # the window size - hte amount of ckuncks we will send befor waiting for ACK
TIMEOUT = 0.5        # timer - in case the ACK gets lost


def run_video_server(my_ip):

    print(f"[*] Video Server starting up. My IP is: {my_ip}")
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

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('0.0.0.0', 8080))
    print("RUDP Video Server is up and listening on port 8080...")

    while True:
        # 1. recieving request from client 
        server_socket.settimeout(None) # canceling the timer when we are just waiting for a new client
        try:
            data, client_address = server_socket.recvfrom(1024)
        except Exception:
            continue
            
        request = data.decode()
        print(f"\n[+] Request: '{request}' from {client_address}")

        try:
           # Splitting the request to the 3 parameters we get
            video_name, quality_level, frame_num_str = request.split()
            frame_num = int(frame_num_str)  
            # Opening a "pipe" to the video file so we can extract information from it
            cap = cv2.VideoCapture(video_name)
            if cap.isOpened() == False:
                print(f"[-] Couldn't open the video {video_name}, try again\n")
                continue
                
            # Jumping to the requested frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            
            # Reading the requested frame
            success, img = cap.read() 
            if success == False:
                print(f"[-] Couldn't read frame {frame_num}, try again\n")
                cap.release() # important to close if we fail
                continue

            # Checking the requested quality
            if quality_level == "Medium":
                img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
            elif quality_level == "Low":
                img = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
                
            cap.release()
            
                
            _, encoded_img = cv2.imencode('.jpg', img)
            bytes_to_send = encoded_img.tobytes()

            # 3. calculate the amount of pieces
            total_chunks = math.ceil(len(bytes_to_send) / CHUNK_SIZE)
            print(f"[*] Image size: {len(bytes_to_send)} bytes. Splitting into {total_chunks} chunks.")

            # Preparing all packets in advance 
            packets = []
            for seq_num in range(total_chunks):
                # finding the starting & the ending point of the current chunck
                start = seq_num * CHUNK_SIZE
                end = start + CHUNK_SIZE
                chunk_data = bytes_to_send[start:end]
                
                # packing the header. '!I I' means - 2 integers (Sequence Number, Total Chunks)
                header = struct.pack('!I I', seq_num, total_chunks)
                
                # connecting header to data
                packet = header + chunk_data
                packets.append(packet)

            # 4. slicing & sending (the base for RUDP) - Sliding Window implementation
            # this method is the main implementation of the reliable data transform mechanism
            base = 0         # The first unacked packet in the window
            next_seqnum = 0  # The next packet to be sent

            while base < total_chunks:
                # send the unsent packets in the window
                while next_seqnum < base + WINDOW_SIZE and next_seqnum < total_chunks:
                    server_socket.sendto(packets[next_seqnum], client_address)
                    next_seqnum += 1

                # setting the timout of the socket to not be stuck in an endless reading
                server_socket.settimeout(TIMEOUT) 
                
                try:
                    # get the responses (ACKs from client)
                    ack_data, _ = server_socket.recvfrom(1024)
                    
                    # unpacking the ACK number (1 integer)
                    ack_num = struct.unpack('!I', ack_data)[0]
                    print(f"[*] Server received Ack: {ack_num}")
                    
                    # if the received ack is bigger than the last acked packet -> move the window
                    if ack_num >= base:
                        base = ack_num + 1

                except socket.timeout:
                    # if you haven't received a moving window ack till timeout -> resend the window
                    print(f"[-] Timeout... Resending window starting from chunk {base}")
                    next_seqnum = base

            print("[+] All chunks sent and ACKed successfully!")

        except Exception as e:
            print(f"[-] Error processing request: {e}")

if __name__ == "__main__":
    my_ip = get_local_ip()
    run_video_server(my_ip)