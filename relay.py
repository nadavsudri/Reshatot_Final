import socket
import struct

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

# Offer - part 2
def run_dhcp_relay():
    print("   Starting DHCP Relay Agent Setup...    ")
    # Asking the user to enter their router's IP. Strip() method cleans spaces ans anything else 
    real_dhcp_server = input("Please enter the real Router's IP address (e.g., 192.168.1.1): ").strip()
    # Checking the local IP in the net
    my_relay_ip = get_local_ip()
    print(f"\n[+] Target Router IP set to: {real_dhcp_server}")
    print(f"[+] Detected local Relay IP: {my_relay_ip}\n")

    # Opening a UDP socket safely
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as e:
        print(f"CRITICAL ERROR: Failed to create socket. OS Error: {e}")
        return
   
    # '0.0.0.0' means - listen to all broadcast requests in the network
    try:
        server_socket.bind(('0.0.0.0', 67))
        print("DHCP Relay Agent is up and listening on port 67...")
    except OSError:
        print("CRITICAL ERROR: Port 67 is already in use. Did you run the terminal as Administrator / with 'sudo'?")
        server_socket.close()
        return
    
    server_socket.settimeout(1.0)   #so the power machine will sense the ctrl+c if pressed
    try:
        print("\nWaiting for DHCP requests to relay...")
        while True:
            try:
                # Receive packet from client 
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
                # Case 1 - the packet arrieved from the client
                # 1 = discover, 3 = request
                if msg_type in [1, 3]:
                    print(f"Forwarding Client {client_mac} (XID: {xid}) msg type {msg_type} to Router...")
                    
                    # Slicing the packet and planting the relay's IP in the GIADDR field
                    my_ip_bytes = socket.inet_aton(my_relay_ip)
                    relayed_packet = packet_data[:24] + my_ip_bytes + packet_data[28:]
                    
                    # Sending to the real router on port 67
                    server_socket.sendto(relayed_packet, (real_dhcp_server, 67))

                # Case 2- the packet is from the rauter
                # 2 = offer, 5 = ack
                elif msg_type in [2, 5]:
                    print(f"Forwarding Router's reply (type {msg_type}) to Client {client_mac} (XID: {xid})...")
                    
                    # The client always listens to port 68 so we transmit there
                    server_socket.sendto(packet_data, ('<broadcast>', 68))
            except socket.timeout:
                continue        #if no ctrl+c was pressed keep going, check again next second
    except KeyboardInterrupt:
        # close the socket if ctrl+c has pressed on
        print("\nServer is shutting down... Closing socket.")
        server_socket.close()


def main():
    print("Starting DHCP server process...")
    run_dhcp_relay()

if __name__ == "__main__":
    main()

         
