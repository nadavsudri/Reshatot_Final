from transport import Transport, TCPTransport, RUDPTransport
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
    pass

def download_frames(conn: Transport, video_name: str):
    # runs in a thread, requests frames, pushes to frame_buffer
    pass

def play_video():
    # runs on main thread, drains frame_buffer, displays with cv2
    pass

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

main()