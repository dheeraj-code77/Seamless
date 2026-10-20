# Seamless Shared Network Protocol & Data Contracts

The wire format shared by the Windows desktop client and the Android client.
`protocol.json` holds the same definitions in machine-readable form.

## Ports

| Purpose | Port | Transport |
| --- | --- | --- |
| Service and transfer | `5173` | HTTP |
| Peer discovery | `52400` | UDP broadcast |

## Discovery

The Windows client broadcasts a `SEAMLESS_DISCOVERY` beacon every 2.5 seconds
and listens for the same beacon from other peers. A peer is dropped after 10
seconds without a beacon.

## Pairing

Two paths reach the same end state — a long-lived device token stored on both
sides.

**QR (zero-touch)** — the QR image encodes a JSON payload with the laptop
address and a single-use pairing token. The phone sends that token to
`POST /api/pair/exchange` and receives a device token in return. The token is
valid for 10 minutes, can be redeemed once, and only the three most recent
tokens stay valid.

**PIN (fallback)** — the laptop shows a 6-digit PIN from
`POST /api/pair/request`. The phone sends it to `POST /api/pair/verify` and
receives a device token. The PIN is valid for 5 minutes.

The device token is sent in the `X-Seamless-Token` header. Requests that carry
a token belonging to a paired device are allowed; anything else is answered
with `401`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/pair/qr` | Pairing QR code as SVG, with a fresh token on every render |
| GET | `/api/device/info` | Device identity, address, receiving folder, clipboard state |
| GET | `/api/devices` | Discovered and paired devices |
| GET | `/api/pair/active_pin` | The PIN currently shown in the pairing dialog |
| GET | `/api/transfer/status` | Live progress of the active transfer |
| GET | `/api/clipboard` | Current clipboard text (paired devices only) |
| GET | `/api/history` | Transfer history entries |
| POST | `/api/pair/request` | Generate a 6-digit PIN |
| POST | `/api/pair/exchange` | Redeem a QR pairing token |
| POST | `/api/pair/verify` | Redeem a PIN |
| POST | `/api/pair/unpair` | Remove a paired device |
| POST | `/api/transfer/send` | Chunked file upload |
| POST | `/api/transfer/pause` · `/api/transfer/resume` · `/api/transfer/cancel` | Transfer controls |
| POST | `/api/history/clear` | Clear the history |
| POST | `/api/settings/folder` | Set the receiving folder |
| POST | `/api/settings/clipboard` | Turn clipboard sync on or off |
| POST | `/api/settings/open_folder` | Open the receiving folder in Explorer |
| POST | `/api/clipboard` | Push clipboard text to the laptop (paired devices only) |

## File transfer

The body of `POST /api/transfer/send` is the raw file, streamed in chunks.
Metadata travels in the `X-Seamless-*` headers. The server hashes the stream as
it arrives and compares the digest with `X-Seamless-SHA256`; a mismatch
deletes the partial file and answers with `400`.

Filenames are sanitised before use, so a name containing `../` cannot escape
the receiving folder, and an existing file gets a numeric suffix instead of
being overwritten.

## Static clients

| Path | Content |
| --- | --- |
| `/` | Windows desktop interface |
| `/mobile` | Android interface |
| `/app.js` · `/mobile-app.js` | Client controllers |
| `/manifest.json` · `/icon.png` · `/icon-512.png` · `/favicon.png` | Web app manifest and icons |
