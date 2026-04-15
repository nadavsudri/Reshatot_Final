import socket
import cv2
import numpy as np
import struct
import time
import threading
import queue
import os

# Creating a buffer that is able to hold up to 30 ready frames  
frame_buffer = queue.Queue(maxsize=30)


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

# This method is in charge of pulling the frames we downloaded to the buffer and show them
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

def run_video_client():
    video_name = input("Which video would you like to play?\n")
    # We want the download_frames & run_video_client to run concurrently so we use threading
    downloader_thread = threading.Thread(target=download_frames, args=(video_name,))
    
    # Start running the download method, the compiler will keep reading the next lines run
    downloader_thread.start()

    play_video()
    print("Client closed successfully.\n")

if __name__ == "__main__":
    run_video_client()