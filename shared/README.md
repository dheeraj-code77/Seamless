# Seamless Shared Network Protocol & Data Contracts

This directory contains the protocol definitions, data schemas, and contracts shared between the Windows desktop application and the Android mobile application.

## Communication Channels

1. **Discovery (UDP Broadcast / mDNS)**
   - Port: `52400` (UDP)
   - Payload: JSON beacon containing device name, device type (`windows` | `android`), IP address, HTTP service port, and pairing status.

2. **Secure Pairing & Handshake (HTTP / REST)**
   - Port: `5173` (HTTP)
   - Endpoints:
     - `GET /api/device/info` -> Device identity and capabilities
     - `POST /api/pair/request` -> Initiates pairing session with 6-digit PIN
     - `POST /api/pair/verify` -> Verifies PIN and returns session token

3. **High-Speed File Transfer (Streaming HTTP)**
   - Endpoints:
     - `POST /api/transfer/send` -> Chunked file streaming with SHA-256 validation
     - `GET /api/transfer/status/:id` -> Real-time progress monitoring
     - `POST /api/transfer/cancel/:id` -> Cancel ongoing transfer

4. **Clipboard Synchronization (WebSocket / HTTP Event)**
   - Endpoints:
     - `POST /api/clipboard/sync` -> Real-time text clipboard exchange
