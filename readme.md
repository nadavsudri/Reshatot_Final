# Video Streaming System

A comprehensive end-to-end video streaming platform implementing core networking protocols from first principles, including DHCP, DNS, and a custom Reliable UDP transport layer.

## Overview

This project demonstrates the design and implementation of a production-grade video streaming ecosystem. The system consists of three interdependent server components that work in concert to deliver adaptive bitrate video content to connected clients. All network protocols are implemented without relying on external networking libraries, providing insight into the mechanics of real-world distributed systems.

## Architecture

The system comprises four principal components:

### Server Components

**DHCP Server** (`dhcp_server.py`)
Dynamically assigns IP addresses to clients within the 192.168.1.100-200 range. Implements the full DHCP four-way handshake (DISCOVER, OFFER, REQUEST, ACK) with support for configuration options including subnet mask, default gateway, broadcast address, lease time, and DNS server information.

**DNS Server** (`dns_server.py`)
Provides name resolution for internal services. Supports dynamic server registration through broadcast messages and forwards unresolved queries to external DNS servers. Maintains a local cache of resolved addresses to minimize external queries.

**Video Server** (`video_server.py`)
Delivers video frames to clients using dual transport protocols. Supports both TCP for reliable streaming and custom Reliable UDP (RUDP) for optimized throughput. Implements on-demand frame extraction and adaptive quality encoding based on client bandwidth requirements.

### Client Application

**Streaming Client** (`user_client.py`)
Implements a feature-rich video player with adaptive bitrate streaming (DASH). The client dynamically adjusts video quality based on measured network latency, allowing seamless playback across varying network conditions. Supports both TCP and RUDP transports with a unified abstraction layer.

## Features

- Full DHCP implementation with RFC 2131 compliance
- Custom DNS resolver with dynamic service registration
- Adaptive bitrate streaming (DASH) with real-time quality adjustment
- Dual transport protocol support (TCP and Reliable UDP)
- Custom Reliable UDP implementation with windowed acknowledgments
- Frame-level quality control (Low: 640x360, High: full resolution)
- Persistent connection support for sequential video streaming
- Thread-safe frame buffering with configurable queue size
- Comprehensive error handling and timeout management

## Requirements

### Dependencies

**Python Standard Library** (no installation required)
- socket, struct, threading, queue
- time, os, base64, json, random

**External Packages**
```
opencv-python >= 4.0.0
numpy >= 1.19.0
```

**Minimum Python Version:** 3.8

### System Requirements

- Minimum 512 MB RAM for video processing
- Video files in MP4 format
- Network interface with broadcast capability
- UDP and TCP ports: 67, 68 (DHCP), 53 (DNS), 80 (HTTP), 8080 (RUDP)

## Installation

### Setup

1. Clone or download the project directory
2. Install dependencies:
```bash
pip install opencv-python numpy
```

### Directory Structure

```
project/
├── dhcp_server.py
├── dns_server.py
├── video_server.py
├── user_client.py
├── transport.py
└── common/
    └── Reliable_udp/
        └── __init__.py
```

Place video files (MP4 format) in the same directory as video_server.py or in a `videos/` subdirectory.

## Usage

### Starting the System

The system must be started in the following order:

**Terminal 1: DNS Server**
```bash
sudo python3 dns_server.py
```

**Terminal 2: DHCP Server**
```bash
sudo python3 dhcp_server.py
```

**Terminal 3: Video Server**
```bash
sudo python3 video_server.py
```

**Terminal 4: Client**
```bash
python3 user_client.py
```

### Client Workflow

1. The client automatically requests an IP address via DHCP
2. Resolve the video server address via DNS
3. Select transport protocol (TCP or RUDP)
4. Request video playback by filename
5. Video begins streaming with adaptive quality adjustment
6. Select subsequent videos without reconnecting

## Technical Details

### DHCP Implementation

The DHCP server implements a complete lease-based IP allocation system with support for configuration options. All required DHCP options are included:

- Option 1: Subnet Mask (255.255.255.0)
- Option 3: Router/Gateway IP
- Option 28: Broadcast Address
- Option 51: IP Address Lease Time (3600 seconds)
- Option 54: Server Identifier

### DNS Implementation

The DNS server handles both internal name resolution and forwarding. Internal services register via broadcast messages in the format:
```
REGISTER <domain> <ip_address>
```

Unresolved queries are forwarded to Google's public DNS (8.8.8.8) with response caching.

### Reliable UDP Protocol

The custom RUDP implementation provides reliable message delivery over UDP through:

- Sequence-based packet numbering
- Sliding window acknowledgment system
- Configurable window size (default: 4 packets)
- Automatic retransmission on timeout
- JSON-encoded headers for protocol information

Default configuration:
- Window size: 4 packets
- Maximum message size: 1024 bytes
- Timeout: 2 seconds
- Socket timeout: 0.5 seconds

### Adaptive Bitrate Streaming

The client measures frame delivery latency and adjusts quality accordingly:

- Latency < 50ms: High quality (full resolution)
- Latency 50-100ms: Medium quality
- Latency > 100ms: Low quality (640x360)

## Protocol Specifications

### DHCP Message Flow
```
Client → Server: DISCOVER (broadcast)
Server → Client: OFFER (broadcast)
Client → Server: REQUEST (broadcast)
Server → Client: ACK (broadcast)
```

### DNS Query Format
```
Client → Server: DNS query (UDP port 53)
Server → Client: DNS response (UDP port 53)
```

### Video Streaming Request
```
Client → Server: GET /filename.mp4/quality/frame_number HTTP/1.1
Server → Client: HTTP/1.1 200 OK + base64-encoded JPEG frame
```

## Project Structure

```
dhcp_server.py (408 lines)
  - DHCP protocol implementation
  - IP pool management
  - Lease tracking

dns_server.py (163 lines)
  - DNS query parsing
  - Dynamic service registration
  - External DNS forwarding

video_server.py (168 lines)
  - Dual protocol support (TCP/RUDP)
  - Frame extraction and encoding
  - Client connection handling

user_client.py (380 lines)
  - DHCP client
  - DNS resolution
  - Video streaming with DASH
  - Playback control

transport.py (61 lines)
  - Protocol abstraction layer
  - Unified TCP/RUDP interface

Reliable_udp/__init__.py (280 lines)
  - Custom RUDP implementation
  - Window management
  - ACK processing
```

## Performance Considerations

### Network Bandwidth

Frame size varies based on quality and content:
- Low quality (640x360): 15-30 KB per frame
- Medium quality: 30-50 KB per frame
- High quality (full): 50-100 KB per frame

At 30 FPS, bandwidth requirements:
- Low: 450-900 Kbps
- Medium: 900-1500 Kbps
- High: 1500-3000 Kbps

### Memory Usage

The frame buffer maintains up to 30 frames in memory:
- Frame buffer: 30 frames × 100 KB = 3 MB maximum
- Protocol overhead: RUDP windows, DNS cache
- Total estimated: 5-10 MB for normal operation

## Limitations and Known Issues

- Single-client per connection (non-concurrent)
- Fixed IP range (192.168.1.x)
- Requires sudo for port binding on Unix systems
- RUDP state reset required between consecutive video streams
- No encryption or authentication
- No support for live streaming
- Video files must be pre-encoded in MP4 format

## Future Enhancements

- Multi-client support with connection pooling
- TLS/SSL encryption
- Authentication and access control
- Live streaming support
- Improved RUDP congestion control
- Hardware acceleration for video encoding
- Support for additional video codecs

## References

- RFC 2131: Dynamic Host Configuration Protocol
- RFC 1035: Domain Names - Implementation and Specification
- RFC 793: Transmission Control Protocol

## License

This project is provided for educational purposes.

## Authors

Developed as a comprehensive networking systems project demonstrating protocol implementation and distributed system design.