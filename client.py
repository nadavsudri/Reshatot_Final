import struct
import random
import socket


def run_dhcp_client():
    # Discover - part 1
    # Header
    # Basic data:
    OP = 1                              # Request (response = 2)
    HTYPE = 1                           # Hardware Typ - ethernet
    HLEN = 6                            # Hardware Address Length (MAC) 
    HOPS = 0  
    XID = random.randint(0, 0xFFFFFFFF) # Transaction ID
    SECS = 0                            # Seconds
    FLAGS = 0 
    # Packing
    header = struct.pack('!B B B B I H H', OP, HTYPE, HLEN, HOPS, XID, SECS, FLAGS)

    # IP adresses:
    CIADDR = socket.inet_aton("0.0.0.0")  # Client IP
    YIADDR = socket.inet_aton("0.0.0.0")  # Your IP
    SIADDR = socket.inet_aton("0.0.0.0")  # Server IP
    GIADDR = socket.inet_aton("0.0.0.0")  # Gateway IP
    mac_bytes = bytes.fromhex("aabbccddeeff")
    CHADDR = mac_bytes + (b'\x00' * 10) 
    SNAME = b'\x00' * 64   # 64 bytes of 0
    FILE = b'\x00' * 128   # 128 bytes of 0
    # Packing IP addresses, MAC, and padding (Part 2)
    header_part2 = struct.pack('!4s 4s 4s 4s 16s 64s 128s', CIADDR, YIADDR, SIADDR, GIADDR, CHADDR, SNAME, FILE)

    # Padding
    magic_cookie = b'\x63\x82\x53\x63'          # DHCP Magic Cookie (Identifies DHCP packet)       
    # !B B B = Type, Length, Value
    option_53 = struct.pack('!B B B', 53, 1, 1) # DHCP Message Type (1 = Discover)
    option_end = struct.pack('!B', 255)         
    # Final packet assembly
    final_packet = header + header_part2 + magic_cookie + option_53 + option_end


    # Opening a UDP socket safely
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # the ability to broadcast 
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError as e:
        print(f"CRITICAL ERROR: Failed to create or configure socket. Details: {e}")
        return
    # Tending the request (broadcast), using the 6767 port so it runs on any computer
    client_socket.sendto(final_packet, ('<broadcast>', 6767))
    print("Waiting for DHCP Offer...")
    # Response_data = buffer, server_address = IP of client + port
    response_data, server_address = client_socket.recvfrom(1024) # Returns a tuple of 2 elements
    if len(response_data) < 243:
        print("Received a packet that is too short. Ignoring.")
        client_socket.close()
        return
    print(f"Received response from {server_address}!")
    
    # By the method parse_offer_packet we'll exstract the xid & offered IP 
    received_xid, offered_ip = parse_offer_packet(response_data)
    # check if the respond really belongs to this client by comparing the xids
    if received_xid == XID:
        print(f"XID match! The server offered us IP: {offered_ip}")
        # Buileding the Request
        #The server's IP is in the 0 index in the server_address tuple
        server_ip_str = server_address[0] 
        request_packet = create_request_packet(XID, offered_ip, server_ip_str, mac_bytes)
        #sending to all other servers by broadcast that we picked this server
        client_socket.sendto(request_packet, ('<broadcast>', 6767))
        print(f"Sent DHCP Request for IP {offered_ip} to server {server_ip_str}...")
        print("Waiting for final DHCP ACK...")
        # Receiving ack - part 4
        ack_data, ack_address = client_socket.recvfrom(1024)
        if len(ack_data) < 243:
            print("Received a packet that is too short. Ignoring.")
            client_socket.close()
            return
        ack_xid, final_ip = parse_offer_packet(ack_data)
        if ack_xid == XID:
            print(f"Received DHCP ACK from {ack_address[0]}.")
            print(f"My new IP address is officially: {final_ip}")
        else:
            print("Received an ACK, but the XID didn't match.")
    else:
        print(f"XID mismatch! Expected {XID} but got {received_xid}. Ignoring packet.")
    client_socket.close()



def parse_offer_packet(packet_data : bytes) -> tuple:
    try:
        received_xid = struct.unpack('!I', packet_data[4:8])[0]          # exstract the xid
        offered_ip_bytes = struct.unpack('!4s', packet_data[16:20])[0]   # exstract the offered IP
        offered_ip_str = socket.inet_ntoa(offered_ip_bytes)              # turnning the IP to a readble str
        return received_xid, offered_ip_str                              # return as a tuple
        
    except struct.error:
        # If the packet arrived corrupted or wrong
        print("Error: Packet structure is corrupted.")
        return None, None

# Request - part 3
def create_request_packet(xid: int, requested_ip: str, server_ip: str, mac_bytes: bytes) -> bytes:
    #header
    #basic data:
    OP = 1    # Request (respons = 2)
    HTYPE = 1 # Hardware Typ - ethernet
    HLEN = 6  # Hardware Address Length (MAC) 
    HOPS = 0  
    XID = xid
    SECS = 0  # Seconds
    FLAGS = 0 
    #packing
    header = struct.pack('!B B B B I H H', OP, HTYPE, HLEN, HOPS, XID, SECS, FLAGS)

    #IP adresses:
    CIADDR = socket.inet_aton("0.0.0.0")  # Client IP
    YIADDR = socket.inet_aton("0.0.0.0")  # Your IP
    SIADDR = socket.inet_aton("0.0.0.0")  # Server IP
    GIADDR = socket.inet_aton("0.0.0.0")  # Gateway IP
    CHADDR = mac_bytes + (b'\x00' * 10) 
    SNAME = b'\x00' * 64   # 64 bytes of 0
    FILE = b'\x00' * 128   # 128 bytes of 0
    # Packing IP addresses, MAC, and padding (Part 2)
    header_part2 = struct.pack('!4s 4s 4s 4s 16s 64s 128s', CIADDR, YIADDR, SIADDR, GIADDR, CHADDR, SNAME, FILE)

    #padding
    magic_cookie = b'\x63\x82\x53\x63'          # DHCP Magic Cookie (Identifies DHCP packet)       
    # !B B B = Type, Length, Value
    option_53 = struct.pack('!B B B', 53, 1, 3) # DHCP Message Type (3 = Request)
    # packing the requested IP 
    requested_ip_bytes = socket.inet_aton(requested_ip)
    option_50 = struct.pack('!B B 4s', 50, 4, requested_ip_bytes)
    # letting all the other servers know that we request a specific IP from a specific server
    server_ip_bytes = socket.inet_aton(server_ip)
    option_54 = struct.pack('!B B 4s', 54, 4, server_ip_bytes)
    option_end = struct.pack('!B', 255)         
    #final packet assembly
    final_packet = header + header_part2 + magic_cookie + option_53 + option_50 + option_54 + option_end
    return final_packet




def main():
    print("Starting DHCP Client process...")
    run_dhcp_client()

if __name__ == "__main__":
    main()