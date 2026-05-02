import socket
import struct
from scapy.all import IP, ICMP, sr1
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
    
#cheking using scapy's icmp echo (ping) to the target to see if its free
def is_ip_available(target_ip):
    # Construct the ICMP Echo Request (Ping)
    packet = IP(dst=target_ip) / ICMP()
    # sr1 sends the packet and waits for a response
    # timeout=0.5: wait half a second
    # verbose=0: don't print Scapy's internal logs
    reply = sr1(packet, timeout=0.5, verbose=0)
    # If reply is None, no one responded (IP is likely free)
    if reply is None:
        return True
    # If we got a reply, the IP is in use
    return False
def get_network_prefix(ip: str) -> str:
    # "192.168.1.50" -> ("192.168.1", ".", "50") -> returns index [0]
    return ip.rpartition('.')[0]

# Offer - part 2
def run_dhcp_server(server_ip : str): 
    # Opening a UDP socket safely
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as e:
        print(f"CRITICAL ERROR: Failed to create socket. OS Error: {e}")
        return
    #'0.0.0.0' means - listen to all broadcast requests in the network
    try:
        server_socket.bind(("0.0.0.0", 67))
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        print("DHCP Server is up and listening on port 67...")
    except OSError:
        print("CRITICAL ERROR: Port 67 is already in use. Please close other instances and try again.")
        server_socket.close()
        return
    
    # Asking for DNS IP address so the offer&ack packets will contain it
    print("\n[*] Looking for DNS Server...")
    dns_ip = ""
    while True:
        server_socket.sendto("WHO_IS_DNS".encode('ascii'), ('<broadcast>', 53))
        server_socket.settimeout(2.0)
        try:
            packet_data, addr = server_socket.recvfrom(1024)
            msg = packet_data.decode('latin-1')
            if msg.startswith("I_AM_DNS"):
                dns_ip = msg.split()[1]
                print(f"[+] Found DNS Server at IP: {dns_ip}\n")
                break
        except socket.timeout:
            print("[*] No DNS response, retrying...")
            continue
    server_socket.settimeout(1.0)
    # Creating IP addresses in the range 200 of current subnet.
    ip_pool = [f"{get_network_prefix(server_ip)}.{i}" for i in range(21, 200)]
    leased_ips = {}                 #holds the used IP's
    server_socket.settimeout(1.0)   #so the power machine will sense the ctrl+c if pressed
    try:
        print("\nWaiting for DHCP requests...")
        while True:
            try:
                #receive packet from client 
                packet_data, client_address = server_socket.recvfrom(1024)
                # In case the server got a wrong message or corrupted one
                if len(packet_data) < 243:
                    print(f"Warning: Received malformed packet from {client_address}. Ignoring.")
                    continue
                print(f"Received a packet from {client_address}!")

                # The unpack method returns a tuple, [0] = take the element in index 0
                try:
                    xid = struct.unpack('!I', packet_data[4:8])[0]              #exstract the transection ID 
                    mac_padded = struct.unpack('!16s', packet_data[28:44])[0]   #exstract the MAC address
                    client_mac = mac_padded[:6].hex()                           #slice the first 6 bytes and translate to hexa
                    # Checking which type of message is this
                    msg_type = packet_data[242]
                except struct.error:
                    print(f"Error: Corrupted packet structure from {client_address}. Ignoring.")
                    continue

                if msg_type == 1:
                    print(f"Received Discover! MAC: {client_mac}, XID: {xid}")
                    if client_mac in leased_ips:
                        offered_ip = leased_ips[client_mac]
                    while len(ip_pool) > 0:
                        offered_ip = ip_pool.pop(0) 
                        if offered_ip==server_ip:continue
                        if  is_ip_available(offered_ip):  
                                      #pop also eareses the ip from the pool
                            leased_ips[client_mac] = offered_ip       #add client & ip to the list
                            print(f"New client MAC {client_mac}! Assigned IP: {offered_ip}")
                            break
                    else:
                        print(f"Sorry MAC {client_mac}, no more IPs available!")
                        continue

                    offer_packet = create_offer_packet(xid, offered_ip, mac_padded, server_ip, dns_ip)     #creating the offer packet
                    server_socket.sendto(offer_packet, ('255.255.255.255', 6868))                  #sending the client the offer
                    print(f"Sent DHCP Offer ({offered_ip}) back to client!\n")


                elif msg_type == 3:
                    print(f"Received Request! MAC: {client_mac}, XID: {xid}")
                    # Checking if the client is really in the list
                    if client_mac in leased_ips:
                        final_ip = leased_ips[client_mac]
                        ack_packet = create_ack_packet(xid, final_ip, mac_padded, server_ip, dns_ip)
                        server_socket.sendto(ack_packet, ('255.255.255.255', 6868))
                        print(f"Sent DHCP ACK ({final_ip}) to client.\n")
                    else:
                        print("Received Request from unknown MAC. Ignoring.")
                elif msg_type == 7:  # RELEASE
                    print(f"Received Release from MAC {client_mac}, releasing IP {leased_ips.get(client_mac, 'unknown')}")
                    if client_mac in leased_ips:
                        ip_to_release = leased_ips.pop(client_mac)
                        ip_pool.append(ip_to_release)  # Return IP to pool
                        print(f"IP {ip_to_release} released back to pool")
            except socket.timeout:
                continue        #if no ctrl+c was pressed keep going, check again next second
    except KeyboardInterrupt:
        # close the socket if ctrl+c has pressed on
        print("\nServer is shutting down... Closing socket.")
        server_socket.close()


def create_offer_packet(xid : int, offered_ip : str, client_mac_bytes : bytes, server_ip : str, dns_ip : str) -> bytes:
    #header
    #basic data:
    OP = 2    # Respons = 2
    HTYPE = 1 # hardware type - set to ethernet
    HLEN = 6  # Mac adress length
    HOPS = 0  
    XID = xid
    SECS = 0  # Seconds
    FLAGS = 0 
    #packing
    header = struct.pack('!B B B B I H H', OP, HTYPE, HLEN, HOPS, XID, SECS, FLAGS)

    #IP adresses:
    CIADDR = socket.inet_aton("0.0.0.0")    # Client IP
    YIADDR = socket.inet_aton(offered_ip)   # Offered ip
    SIADDR = socket.inet_aton(server_ip)    # Server IP
    GIADDR = socket.inet_aton("0.0.0.0")    # Gateway IP - relay agent [relevant for different subnet client - server relation]
    CHADDR = client_mac_bytes
    
    SNAME = b'\x00' * 64   #server domain name. id dosent have a dimain name so 64 bytes of 0
    FILE = b'\x00' * 128   #path to a file that can be received from the dhcp server [for boots and such] not needed, so 128 bytes of 0
    # Packing IP addresses, MAC, and padding (Part 2)
    header_part2 = struct.pack('!4s 4s 4s 4s 16s 64s 128s', CIADDR, YIADDR, SIADDR, GIADDR, CHADDR, SNAME, FILE)
    #padding
    magic_cookie = b'\x63\x82\x53\x63'            # DHCP Magic Cookie (Identifies DHCP packet)       
    # !B B B = Type, Length, Value
    option_53 = struct.pack('!B B B', 53, 1, 2)   # DHCP Message Type (2 = offer)
    # This option transfers the client the DNS IP
    dns_id = socket.inet_aton(dns_ip)
    option_6 = struct.pack('!B B 4s', 6, 4, dns_id)
    # Tells the client it is the end of the options
    option_end = struct.pack('!B', 255)
    #we'll add subnet musk to the offer packet
    subnet_mask = socket.inet_aton("255.255.255.0")
    option_1 = struct.pack('!B B 4s', 1, 4, subnet_mask) 
    # #return the server identifier
    server_id = socket.inet_aton(server_ip)
    option_54 = struct.pack('!B B 4s', 54, 4, server_id)     
    #final packet assembly
    final_packet = header + header_part2 + magic_cookie + option_53 + option_1 + option_54 + option_6 + option_end
    return final_packet


def create_ack_packet(xid : int, offered_ip : str, client_mac_bytes : bytes, server_ip : str, dns_ip : str) -> bytes:
    #header
    #basic data:
    OP = 2    # Respons = 2
    HTYPE = 1 # Hardware Typ - ethernet
    HLEN = 6  # Hardware Address Length (MAC) 
    HOPS = 0  
    XID = xid
    SECS = 0  # Seconds
    FLAGS = 0 
    #packing
    header = struct.pack('!B B B B I H H', OP, HTYPE, HLEN, HOPS, XID, SECS, FLAGS)

    #IP adresses:
    CIADDR = socket.inet_aton("0.0.0.0")    # Client IP
    YIADDR = socket.inet_aton(offered_ip)   # Offered ip
    SIADDR = socket.inet_aton(server_ip)    # Server IP
    GIADDR = socket.inet_aton("0.0.0.0")    # Gateway IP

    CHADDR = client_mac_bytes
    SNAME = b'\x00' * 64   # 64 bytes of 0
    FILE = b'\x00' * 128   # 128 bytes of 0
    # Packing IP addresses, MAC, and padding (Part 2)
    header_part2 = struct.pack('!4s 4s 4s 4s 16s 64s 128s', CIADDR, YIADDR, SIADDR, GIADDR, CHADDR, SNAME, FILE)
    
    #padding
    magic_cookie = b'\x63\x82\x53\x63'            # DHCP Magic Cookie (Identifies DHCP packet)       
    # !B B B = Type, Length, Value
    option_53 = struct.pack('!B B B', 53, 1, 5)   # DHCP Message Type (5 = ack)
    # This option transfers the client the DNS IP
    dns_id = socket.inet_aton(dns_ip)
    option_6 = struct.pack('!B B 4s', 6, 4, dns_id)
    # Tells the client it is the end of the options
    option_end = struct.pack('!B', 255)
    # We'll add subnet musk to the ack packet
    subnet_mask = socket.inet_aton("255.255.255.0")
    option_1 = struct.pack('!B B 4s', 1, 4, subnet_mask) 
    
    # #return the server identifier
    server_id = socket.inet_aton(server_ip)
    option_54 = struct.pack('!B B 4s', 54, 4, server_id) 
    option_3  = struct.pack('!B B 4s', 3, 4, server_id)     
    #final packet assembly
    final_packet = header + header_part2 + magic_cookie + option_53 + option_1 + option_54 + option_6 +option_3+ option_end

    return final_packet

def main():
    print("Starting DHCP server process...")
    server_ip = get_local_ip()
    run_dhcp_server(server_ip)

if __name__ == "__main__":
    main()

         
