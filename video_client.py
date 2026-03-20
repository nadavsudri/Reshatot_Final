import socket
import cv2
import numpy as np
import struct
import time
import threading
import queue

# Creating a buffer that is able to hold up to 30 ready frames  
frame_buffer = queue.Queue(maxsize=30)

def download_frames(video_name):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('127.0.0.1', 8080)
    client_socket.settimeout(2.0)
    current_quality = "Low"
    frame_num = 1    # In order to keep up with the numbers of frames that where sent

    # 1. The client requests a high-quality frame
    while True:
        # Separate the request elements 
        request_msg = f"{video_name} {current_quality} {frame_num}\n"
        print(f"Requesting: {request_msg}")

        # in order to know which qualitiy level we can provide, we measure the time it 
        # takes to provide a low quality frame.
        starting_time = time.time()
        client_socket.sendto(request_msg.encode(), server_address)

        received_chunks = {}
        total_chunks = -1

        print("Waiting for chunks...")
        
        # --- RUDP RECEIVE & ACK LOGIC ---
        # The following logic is adapted from the 'recv_msg' method in our old Server.py.
        # Instead of receiving JSON over TCP, we receive binary chunks over UDP,
        # store them securely in a dictionary, and send explicit ACKs back to 
        # move the sender's sliding window.
        while True:
            try:
                # 2. Receiving packet from server
                packet, _ = client_socket.recvfrom(65535)
                
                # 3. Unpacking the header (8 bytes)
                header = packet[:8]
                chunk_data = packet[8:]
                seq_num, incoming_total_chunks = struct.unpack('!I I', header)
                
                if total_chunks == -1:
                    total_chunks = incoming_total_chunks
                    
                # 4. Storing the chunk (similar to accumulating the buffer in old recv_msg)
                if seq_num not in received_chunks:
                    received_chunks[seq_num] = chunk_data
                    print(f"[*] Received chunk {seq_num + 1}/{total_chunks}")
                
                # SENDING ACK (Adapted from 'send_ack' method in old code) 
                # We pack the sequence number into a 4-byte integer and send it 
                # back to the server so it knows this specific chunk arrived safely.
                ack_packet = struct.pack('!I', seq_num)
                client_socket.sendto(ack_packet, server_address)
                
                # 5. Check if we received all chunks successfully
                if len(received_chunks) == total_chunks:
                    print("\n[+] All chunks received! Assembling image...")
                    # Send the last ACK a few more times just in case 
                    # it gets lost, preventing the server from a timeout loop.
                    for _ in range(5):
                        client_socket.sendto(ack_packet, server_address)
                    break # Break inner loop, move to image assembly
                    
            except socket.timeout:
                print("[-] Error: Timeout waiting for chunks.")
                break # Break inner loop due to timeout, move to step 6 (which will handle the failure)
        # END OF RUDP LOGIC 

        # 6. Image Assembly
        # Only assemble if we actually got all chunks!
        if len(received_chunks) == total_chunks and total_chunks > 0:
            full_data = b''
            for i in range(total_chunks):
                full_data += received_chunks[i]

            # this method comes from numpy - it gets a long sequence of 0,1 and turns it into an 
            # arranged array.
            # uint8 - divides the data into 8-bit pieces - each pixel is represented by a number in the 
            # range of 0 - 255 -> we need 8 bits to represent these numbers in binary
            np_arr = np.frombuffer(full_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)    

            if img is not None:
                ending_time = time.time()

                # the time it took to deliver the current frame
                frame_time = ending_time - starting_time
                
                # Push img to the queue
                frame_buffer.put(img)

                if frame_time < 0.05:     # if the net is super fast
                    current_quality = "High"
                elif frame_time < 0.1:    # if the net is fine
                    current_quality = "Medium"
                else:
                    current_quality = "Low"
                    print("Network is slow. dropping quality to low for next frame")
            else:
                print("[-] Error: Failed to decode the assembled image.")
            
            # Increment frame number for the next iteration of the while loop
            frame_num += 1

        else:
            # If we didn't get all chunks, it means the server stopped sending (video ended)
            print("[*] Video ended. Exiting download loop.")
            break # Breaks the outer while True loop!

    # Send poison pill to the player thread
    frame_buffer.put(None)


# This method is in charge of pulling the frames we downloaded to the buffer and show them
def play_video():
    while True:
        img = frame_buffer.get()
        if img is None:
            break
        cv2.imshow("My Dash Player", img)
        cv2.waitKey(33)
    # after the video is over, close the window
    print("Finished playing video!")
    cv2.destroyAllWindows()