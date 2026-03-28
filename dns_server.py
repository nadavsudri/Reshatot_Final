import socket , struct

## global var

self_ip = socket.inet_aton("192.168.1.10")
dns_data = {}

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

##exstracting the dns domain from the requst -> [12 bytes of header][domain]
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
    

def run_dns_server(my_ip):
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # inconing dns request socket
    server_socket.bind(("0.0.0.0",53))

    print(f"My IP is: {my_ip}")
    print("Listening on 53 for DNS requests")

    print("[*] Waiting for DHCP to ask for DNS...")
    while True:
        try:
            packet_data, addr = server_socket.recvfrom(1024)
            msg = packet_data.decode('ascii')
            if msg.startswith("WHO_IS_DNS"):
                response = f"I_AM_DNS {my_ip}"
                server_socket.sendto(response.encode('ascii'), addr)
                print(f"[*] Told DHCP my IP: {my_ip}")
                break
        except:
            pass

    while True:
        try:

            packet_data, client_address = server_socket.recvfrom(1024)
            
            # Intercept registration broadcasts from other servers (like the Video Server) to dynamically 
            # update the DNS records
            if packet_data.startswith(b"REGISTER"):
                msg_parts = packet_data.decode('ascii').split()
                # The least length should be at least 3, if not - it could be coruppted or missing
                if len(msg_parts) >= 3:
                    domain_to_register = msg_parts[1]
                    ip_to_register = msg_parts[2]
                    # Inserting the server name & IP to DNS dict
                    dns_data[domain_to_register] = ip_to_register
                    print(f"[+] Server Registered: {domain_to_register} is now mapped to {ip_to_register}")
                continue

            res = parse_dns_request(packet_data)
            res_sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            res_sock.sendto(res,client_address)
            res_sock.close()
        except:
            pass
    
def parse_dns_request(data):
    print("request")
    dns_header_format = "!HHHHHH"
    transaction_id, flags, qdcount, ancount, nscount, arcount = struct.unpack(dns_header_format,data[:12]) #unpacking
    domain,_ = extract_domain_name(data,12)
    if domain in dns_data:
        res = build_dns_response(transaction_id,domain,dns_data[domain])
        return res
    else:
        temp_sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        temp_sock.sendto(data,("8.8.8.8",53))
        google_response, _ = temp_sock.recvfrom(1024)
        dns_data[domain]= extract_ip_from_response(google_response)
        return google_response

def encode_domain_name(domain):
    # Turns "google.com" -> b'\x06google\x03com\x00'
    parts = domain.split('.')
    encoded = b''
    for part in parts:
        encoded += struct.pack("!B", len(part)) + part.encode('ascii')
    return encoded + b'\x00'

def build_dns_response(transaction_id, domain_name, ip_address):
    header = struct.pack("!HHHHHH", transaction_id, 0x8180, 1, 1, 0, 0)

    question = encode_domain_name(domain_name) + struct.pack("!HH", 1, 1)
    answer_fixed = struct.pack("!HHHIH", 0xc00c, 1, 1, 60, 4)

    ip_bytes = socket.inet_aton(ip_address)
    
    return header + question + answer_fixed + ip_bytes

#returns the ip as a string ex. "0.0.0.0"
def extract_ip_from_response(data):
    _, offset = extract_domain_name(data, 12)
    offset += 4
    ip_offset = offset + 12
    ip_raw = data[ip_offset : ip_offset + 4]
    return socket.inet_ntoa(ip_raw)



def main():
    print("Starting DNS server process...")
    my_ip = get_local_ip()
    run_dns_server(my_ip)

if __name__ == "__main__":
    main()