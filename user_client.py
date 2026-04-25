from transport import Transport, TCPTransport, RUDPTransport
import queue, threading
from Reliable_udp import ReliableUDP
import random, socket, struct
import cv2
import numpy as np
import struct
import time
import os
import base64
from datetime import datetime

slowtheweb = False

#Global variabels

def simulate_throttle(data_size_bytes, target_speed_kbps):
    target_bps = target_speed_kbps * 1000
    # Calculate how long this data SHOULD have taken to arrive
    expected_time = (data_size_bytes * 8) / target_bps
    if slowtheweb:
        time.sleep(expected_time)


def disconnect(sock:Transport,dhcp,my_ip,mac):
    print("\n[*] Disconecting from server...")
    sock.send(b"<DISCONNECT>")
    time.sleep(0.5)
    print(["Closing socket"])
    sock.close()
    time.sleep(0.5)
    print(f"Releaseing IP: {my_ip} From MAC {mac}")
    release_ip(my_ip,dhcp,mac)

def choose_connection() -> str:
    return input("Choose Connection type [TCP | UDP]").strip().lower()


def release_ip(my_ip: str, server_ip: str, mac_bytes: bytes):
    """Release the DHCP-assigned IP address back to the server"""
    try:
        XID = random.randint(0, 0xFFFFFFFF)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('0.0.0.0', 68))
        sock.settimeout(2.0)
        
        # DHCP RELEASE packet structure
        OP    = 1
        HTYPE = 1
        HLEN  = 6
        HOPS  = 0
        SECS  = 0
        FLAGS = 0
        
        # Header
        header = struct.pack('!B B B B I H H', OP, HTYPE, HLEN, HOPS, XID, SECS, FLAGS)
        
        # IP addresses
        CIADDR = socket.inet_aton(my_ip)         # Client IP (this time we have one!)
        YIADDR = socket.inet_aton("0.0.0.0")
        SIADDR = socket.inet_aton("0.0.0.0")
        GIADDR = socket.inet_aton("0.0.0.0")
        CHADDR = mac_bytes + (b'\x00' * 10)
        SNAME  = b'\x00' * 64
        FILE   = b'\x00' * 128
        
        header_part2 = struct.pack('!4s 4s 4s 4s 16s 64s 128s',
                                    CIADDR, YIADDR, SIADDR, GIADDR, CHADDR, SNAME, FILE)
        
        # Magic cookie
        magic_cookie = b'\x63\x82\x53\x63'
        
        # Options
        option_53 = struct.pack('!B B B', 53, 1, 7)  # Message type = RELEASE
        option_54 = struct.pack('!B B 4s', 54, 4, socket.inet_aton(server_ip))  # Server identifier
        option_end = struct.pack('!B', 255)
        
        # Assemble RELEASE packet
        release_packet = header + header_part2 + magic_cookie + option_53 + option_54 + option_end
        
        # Send to DHCP server
        sock.sendto(release_packet, ('<broadcast>', 67))
        print(f"[DHCP] Sent RELEASE for IP {my_ip}")
        
        sock.close()
        return True
    
    except Exception as e:
        print(f"[DHCP] RELEASE failed: {e}")
        return False
    
def get_ip() -> tuple:
    try: 
        XID = random.randint(0, 0xFFFFFFFF)
        mac_bytes = random.randbytes(6) #creating fake MAC adreass to identify to the dhcp
        _mac=mac_bytes
        #temp socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('0.0.0.0', 68))
        sock.settimeout(5.0)

        # assembling the dhcp message ----> [request]
        OP    = 1
        HTYPE = 1
        HLEN  = 6
        HOPS  = 0
        SECS  = 0
        FLAGS = 0
        # part 1 - header
        header = struct.pack('!B B B B I H H', OP, HTYPE, HLEN, HOPS, XID, SECS, FLAGS)
        # ip addresses (all zeros, we don't have one yet)
        CIADDR = socket.inet_aton("0.0.0.0")
        YIADDR = socket.inet_aton("0.0.0.0")
        SIADDR = socket.inet_aton("0.0.0.0")
        GIADDR = socket.inet_aton("0.0.0.0")
        CHADDR = mac_bytes + (b'\x00' * 10)
        SNAME  = b'\x00' * 64
        FILE   = b'\x00' * 128
        header_part2 = struct.pack('!4s 4s 4s 4s 16s 64s 128s',
        CIADDR, YIADDR, SIADDR, GIADDR, CHADDR, SNAME, FILE)
        # uniqe dhcp broadcast identifier
        magic_cookie = b'\x63\x82\x53\x63'

        # options
        option_53  = struct.pack('!B B B', 53, 1, 1)  # message type = DISCOVER
        option_end = struct.pack('!B', 255)
        # final assembly
        discover_packet = header + header_part2 + magic_cookie + option_53 + option_end
        #send to port 67
        sock.sendto(discover_packet, ('<broadcast>', 67))
        # infering the response-----------------------> [response]
        offer_data, server_addr = sock.recvfrom(1024)
        # extract XID - bytes 4-8
        received_xid = struct.unpack('!I', offer_data[4:8])[0]

        # extract offered IP - bytes 16-20
        offered_ip = socket.inet_ntoa(offer_data[16:20])

        # walk options to find DNS IP (option 6), starting after magic cookie at byte 240
        dns_ip = None
        i = 240
        while i < len(offer_data):
            opt = offer_data[i]
            if opt == 255:          # END
                break
            if opt == 0:            # PAD
                i += 1
                continue
            length = offer_data[i + 1]
            if opt == 6:            # DNS server option
                dns_ip = socket.inet_ntoa(offer_data[i + 2 : i + 6])
            i += 2 + length

        # verify it's our reply
        if received_xid != XID:
            print("XID mismatch, ignoring")
            return None

        # fixed values - same as discover
        OP    = 1
        HTYPE = 1
        HLEN  = 6
        HOPS  = 0
        SECS  = 0
        FLAGS = 0

        #header
        header = struct.pack('!B B B B I H H', OP, HTYPE, HLEN, HOPS, XID, SECS, FLAGS)

        # ip addresses
        CIADDR = socket.inet_aton("0.0.0.0")
        YIADDR = socket.inet_aton("0.0.0.0")
        SIADDR = socket.inet_aton("0.0.0.0")
        GIADDR = socket.inet_aton("0.0.0.0")
        CHADDR = mac_bytes + (b'\x00' * 10)
        SNAME  = b'\x00' * 64
        FILE   = b'\x00' * 128

        header_part2 = struct.pack('!4s 4s 4s 4s 16s 64s 128s',
                                CIADDR, YIADDR, SIADDR, GIADDR, CHADDR, SNAME, FILE)
        magic_cookie = b'\x63\x82\x53\x63'

        # part 3 - options
        option_53  = struct.pack('!B B B', 53, 1, 3)                              # message type = REQUEST
        option_50  = struct.pack('!B B 4s', 50, 4, socket.inet_aton(offered_ip))  # requested IP
        option_54  = struct.pack('!B B 4s', 54, 4, socket.inet_aton(server_addr[0]))  # server identifier
        option_end = struct.pack('!B', 255)

        # final assembly
        request_packet = header + header_part2 + magic_cookie + option_53 + option_50 + option_54 + option_end

        # send it
        sock.sendto(request_packet, ('<broadcast>', 67))

        ack_data, _ = sock.recvfrom(1024)
        # extract XID - bytes 4-8
        ack_xid = struct.unpack('!I', ack_data[4:8])[0]

        # extract my IP - bytes 16-20
        my_ip = socket.inet_ntoa(ack_data[16:20])

        # verify it's our reply
        if ack_xid != XID:
            print("XID mismatch, ignoring")
            return None
        if ack_xid == XID:
            print(f"[DHCP] Got ACK — my IP is {my_ip}")
        sock.close()
        return (my_ip,dns_ip,server_addr[0],mac_bytes)

    except socket.timeout:
        print("[DHCP] Timeout — is the DHCP server running?")
        return None
    finally:
        sock.close()

def encode_domain_name(domain):
    # Turns "google.com" -> b'\x06google\x03com\x00'
    parts = domain.split('.')
    encoded = b''
    for part in parts:
        encoded += struct.pack("!B", len(part)) + part.encode('ascii')
    return encoded + b'\x00'


def extract_domain_name(dns_domain, offset)-> str:
    labels = []
    while True:
        length = dns_domain[offset]
        if length==0:
            offset+=1
            break
        offset+=1
        labels.append(dns_domain[offset:offset+length].decode("ascii"))
        offset+=length
    return ".".join(labels),offset

def extract_ip_from_response(data):
    _, offset = extract_domain_name(data, 12)
    offset += 4
    ip_offset = offset + 12
    ip_raw = data[ip_offset : ip_offset + 4]
    return socket.inet_ntoa(ip_raw)


def look_for_domain(dns_ip: str, domain: str) -> str:
    #temp socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(5.0)
    # sends DNS query, returns video server ip
    # header
    transaction_id = random.randint(0, 0xFFFF)
    flags          = 0x0100   # standard query
    questions      = 1
    answer_rrs     = 0
    authority_rrs  = 0
    additional_rrs = 0

    header = struct.pack('!H H H H H H',transaction_id, flags, questions,answer_rrs, authority_rrs, additional_rrs)
    # question
    qname  = encode_domain_name(domain)
    qtype  = struct.pack('!H', 1)   # A record
    qclass = struct.pack('!H', 1)   # Internet
    question = qname + qtype + qclass
    # final packet
    dns_query = header + question

    sock.sendto(dns_query,(dns_ip,53))

    response, _ = sock.recvfrom(1024)

    ip = extract_ip_from_response(response)

    sock.close()

    return ip

def connect_to_server(server_ip: str, choice: str) -> Transport:
    # opens socket, handshake, returns TCPTransport or RUDPTransport
    if choice == "tcp":
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (server_ip, 80)
        client_socket.connect(server_address)
        tcp_sock = TCPTransport(client_socket)
        return tcp_sock
    else:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # RUDP from our library
        udp_r = ReliableUDP(client_socket)
        udp_r.connect(server_ip, 8080)
        udp_sock = RUDPTransport(udp_r)
        return udp_sock
    
def creat_http_req(movie_name: str, quality: str, frame_num: int, server_domain):
    req_file = f"{movie_name}.mp4/{quality}/{frame_num}"
    http_request = (
        f"GET /{req_file} HTTP/1.1\r\n"
        f"Host: {server_domain}\r\n"
        f"Accept: video/mp4\r\n" # Tells the server we expecting a video
        f"Connection: keep-alive\r\n"
        f"\r\n" # An necessary empty line
    )
    # Incode to binary format so the socket sent it in bytes
    return http_request.encode('utf-8')



# runs in a thread, requests frames, pushes to frame_buffer
def download_frames(conn: Transport, video_name: str, frame_buffer: queue.Queue, server_ip: str):
    current_quality = "high"
    frame_num = 0

     #reset the rudp connection
    if hasattr(conn, 'reset_for_next_message'):
        conn.reset_for_next_message()
    if hasattr(conn, 'rudp'):
        conn.rudp.sock.settimeout(3.0)
     

    while True:
        request_bytes = creat_http_req(video_name, current_quality, frame_num, server_ip)
        conn.send(request_bytes.decode('utf-8'))
        
        starting_time = time.time()
        received_data = b""
        
        while True:
            part = conn.recv() 
            if isinstance(part,str):
                part = part.encode()
            if not part:
                break  
            received_data += part
            if b"<END_OF_CHUNK>" in received_data:
                received_data = received_data.replace(b"<END_OF_CHUNK>", b"")
                break
            elif b"<END_OF_STREAM>" in received_data:
                received_data = received_data.replace(b"<END_OF_STREAM>", b"")
                end = True
                break
        if not received_data:
            break 

        # 2. Decode and Convert
        try:
            if b"\r\n\r\n" in received_data:
                data_size = int(received_data.split(b"\r\n")[1].split(b":")[1].strip().decode("utf-8"))
              
                received_data = received_data.split(b"\r\n\r\n")[1]
                
            # checking that the frame is ok and not empty
            if not received_data:
                print(f"[-] Frame {frame_num} data too short or empty: {len(received_data)} bytes")
                # frame_num += 1
                break
            # check if 404 has arrived
            if b"404" in received_data[:30]:
                print(f"[*] Frame {frame_num} not found (HTTP 404), video ended")
                break  # Exit cleanly
                
            # print(f"DEBUG: First 50 chars of payload: {received_data.decode()}",type(received_data))
            # Decode Base64 string to raw JPEG bytes
          
            img_bytes = base64.b64decode(received_data)
            # Convert bytes to a numpy array (the bridge to OpenCV)
            nparr = np.frombuffer(img_bytes, np.uint8)
            
            # Decode the JPEG into an actual image frame
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                frame_buffer.put(frame)
                print(f"[*] Buffered frame {frame_num}")
            else:
               
                print(f"[-] Frame {frame_num} was corrupted.")

        except Exception as e:
            print(received_data)
            print(f"[-] Processing error: {e}")
            break
        simulate_throttle(data_size, 2000) # Force a 2 Mbps connection

        # 3. DASH Logic (Based on how fast that one frame arrived)
        chunk_time = time.time() - starting_time
        if chunk_time > 0:
            band_width = (data_size * 8) / (chunk_time * 1000)
        print(f"{band_width} kbp/s")
        
       
        if band_width >5000:     
            current_quality = "High"
        elif band_width > 2000:   
            current_quality = "Medium"
        else:                    
            current_quality = "Low"
        
        # 4. Advance counter
        frame_num += 1
        # if end:break

    frame_buffer.put(None)
    # empty the frame buffer and the socket
    conn.flush()
    # while not frame_buffer.empty():
    #         try:
    #             frame_buffer.get_nowait()
    #         except:
    #             break

# runs on main thread, drains frame_buffer, displays with cv2
def play_video(frame_buffer:queue):
    # This tow lines reasure that the video window will show on top of all the other windows.
    # The first line orders to allocate a real memory area to the video window and opens a normal window
    # The second line orders to always show this window no metter what - sets the WND_PROP_TOPMOST to 1 = true 
    cv2.namedWindow("My Dash Player", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("My Dash Player", cv2.WND_PROP_TOPMOST, 1)
    image_count = 0
    print("\nBuffering video... Please wait a few seconds.\n")
    # Buffering at least 20 frames so the video will run smoothly
    while frame_buffer.qsize() < 30:
        time.sleep(0.1)
    print("Buffering complete! Enjoy the movie.\n")
    while True:
        if not frame_buffer.empty():
            # print(frame_buffer.qsize())
            img = frame_buffer.get()
            if img is None:
                break
            img_resized = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_LINEAR)
            cv2.imshow("My Dash Player", img_resized)
        # Wait for 33 miliseconds between each frame. if q is pressed - stop and go out
        if cv2.waitKey(33) & 0xFF == ord('q'):
            break
    # after the video is over, close the window
    print("Finished playing video!\n")
    
    cv2.destroyAllWindows()
    ## unix closeing issue fix
    for i in range(5):
        cv2.waitKey(1)
    

def main():
    (my_ip,dns_ip,dhcp_ip,my_MAC) = get_ip()
    _ip = my_ip
    while True:
        domain  = input("Where would you like to go (nooshi.video is your only valid option)? >>> ").strip().lower()
        if domain =="nooshi.video":
            break
        else:
            server_ip = look_for_domain(dns_ip,domain)
            print(f"invalid url, the ip you wanted for {domain} is:{server_ip},\nbut no video is there :( ")
    ##masking the real url
    domain = "video.server.local"
    server_ip = look_for_domain(dns_ip,domain)
    print(f"Got: {server_ip} from DNS server")
    

    conn_type = input("What type of connection? [rudp \\ tcp] >>>").lower()
    transport_t = connect_to_server(server_ip,conn_type)
    t_download = None
    
    while True:
        try:
            frame_buffer = queue.Queue(maxsize=30000)
            
            # Creating a buffer that is able to hold up to 30 ready frames  
            if t_download and t_download.is_alive():
                t_download.join(timeout=2)
            while not frame_buffer.empty():
                try:
                    frame_buffer.get_nowait()
                except:
                    break
                
            ## insert later the available videos to play
            video_request = input("Select a video to play>>>")
            print(frame_buffer.qsize()==0)
            t_download = threading.Thread(target=download_frames,args=(transport_t,video_request,frame_buffer,server_ip),daemon=True)
            t_download.start()
            play_video(frame_buffer)
        except KeyboardInterrupt:
            disconnect(transport_t,dhcp_ip,my_ip,my_MAC)
            break

        
       
main()