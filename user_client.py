from transport import Transport, TCPTransport, RUDPTransport
import Reliable_udp 
import random, socket, struct


def choose_connection() -> str:
    return input("Choose Connection type [TCP | UDP]").strip().lower()

def get_ip() -> tuple:
    try: 
        XID = random.randint(0, 0xFFFFFFFF)
        mac_bytes = random.randbytes(6) #creating fake MAC adreass to identify to the dhcp
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
        return (my_ip,dns_ip)

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
    if choice == "TCP":
        socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (server_ip, 80)
        socket.connect(server_address)
        tcp_sock = transport(socket)
        return tcp_sock
    else:
        socket = socket.socke(socket.AF_INET, socket.SOCK_DGRAM)
        # RUDP from our library
        udp_r = ReliableUDP(socket)
        udp_r.connect(server_ip, 8080)
        udp_sock = transport(udp_r)
        return udp_sock
    
def creat_http_req(movie_name: str, quality: str, frame_num: int, server_domain="video.server.local"):
    req_file = f"{movie_name}.mp4_{qualitiy}_{frame_num}"
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


def download_frames(conn, video_name: str, frame_buffer):
    current_quality = "Low"
    frame_num = 0   

    while True:
        # 1. Create the HTTP request (returns bytes)
        request_bytes = creat_http_req(video_name, current_quality, frame_num, server_domain="video.server.local")
        
        # 2. Decode bytes to string because conn.send() expects a string!
        request_str = request_bytes.decode('utf-8')
        
        print(f"Requesting: {video_name}, Quality: {current_quality}, Frame: {frame_num}")
        starting_time = time.time()
        
        # 3. Send the request using your Transport wrapper
        conn.send(request_str)
        print("Waiting for video chunk...")
        
        # 4. Receive the assembled chunk using the <END_OF_CHUNK> tag logic
        # This makes it work perfectly for BOTH your TCP and RUDP transports
        received_str = ""
        while True:
            part = conn.recv() 
            if not part:
                # If recv returns empty, the connection dropped
                break  
            received_str += part
            # Check if we got the "end of chunk" signature
            if "<END_OF_CHUNK>" in received_str:
                # Remove the signature so Base64 can decode cleanly
                received_str = received_str.replace("<END_OF_CHUNK>", "")
                break
        if not received_str:
            print("[*] Video ended or stream broken. Exiting download loop.")
            break 

        # 5. Decode the Base64 text BACK into raw binary video data
        try:
            full_data = base64.b64decode(received_str)
        except Exception as e:
            print(f"[-] Failed to decode video data: {e}")
            break

        # --- CHUNK ASSEMBLY & DASH DECISION ---
        ending_time = time.time()
        chunk_time = ending_time - starting_time
        # 6. Save the binary data to a UNIQUE temporary video file 
        temp_filename = f"temp_chunk_{frame_num}.mp4" 
        
        with open(temp_filename, "wb") as f:
            f.write(full_data)
        # 7. Open the temporary file and extract frames using OpenCV
        cap = cv2.VideoCapture(temp_filename)
        while True:
            ret, frame = cap.read()
            if not ret:
                break 
            frame_buffer.put(frame)
        cap.release()
        # A clean up - deleat the file to save disk space
        try:
            os.remove(temp_filename)
        except OSError as e:
            print(f"Warning: Could not remove temp file {temp_filename}: {e}")

        # 8. DASH Logic
        if chunk_time < 0.5:     
            current_quality = "High"
        elif chunk_time < 0.9:   
            current_quality = "Medium"
        else:                    
            current_quality = "Low"
            print("Network is slow. Dropping quality to Low for the next chunk.\n")
        
        # Advance the frame counter by 30
        frame_num += 30
    # Send poison pill to the video player thread
    frame_buffer.put(None)

   

# runs on main thread, drains frame_buffer, displays with cv2
def play_video():
    # This tow lines reasure that the video window will show on top of all the other windows.
    # The first line orders to allocate a real memory area to the video window and opens a normal window
    # The second line orders to always show this window no metter what - sets the WND_PROP_TOPMOST to 1 = true 
    cv2.namedWindow("My Dash Player", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("My Dash Player", cv2.WND_PROP_TOPMOST, 1)

    print("\nBuffering video... Please wait a few seconds.\n")
    # Buffering at least 20 frames so the video will run smoothly
    while frame_buffer.qsize() < 30:
        time.sleep(0.1)
    print("Buffering complete! Enjoy the movie.\n")
    while True:
        img = frame_buffer.get()
        if img is None:
            break
        cv2.imshow("My Dash Player", img)
        # Wait for 33 miliseconds between each frame. if q is pressed - stop and go out
        if cv2.waitKey(33) & 0xFF == ord('q'):
            break
    # after the video is over, close the window
    print("Finished playing video!\n")
    cv2.destroyAllWindows()

def main():
    (my_ip,dns_ip) = get_ip()
    
    while True:
        domain  = input("Where would you like to go (nooshi.video is your only valid option)? >>> ").strip().lower()
        if domain =="nooshi.video":
            break
        else:
            print("invalid url")
    ##masking the real url
    domain = "video.server.local"
    server_ip = look_for_domain(dns_ip,domain)
    print(f"Got: {server_ip} from DNS server")

    # Creating a buffer that is able to hold up to 30 ready frames  
    frame_buffer = queue.Queue(maxsize=30)

main()