# Seamless Windows Desktop Application

The desktop client. It runs a local HTTP service, announces itself on the
network, and serves the desktop interface to a native window.

## Layout

```
src/
├── main.py             Entry point: starts the server and opens the window
├── core/
│   ├── config.py       Local IP detection, receiving folder, config file
│   ├── server.py       HTTP routes, chunked streaming, static file serving
│   ├── discovery.py    UDP broadcast beacon on port 52400
│   ├── security.py     PINs, pairing tokens, device tokens, path sanitising
│   ├── transfer_engine.py  Live progress, throughput, pause/cancel state
│   ├── clipboard.py    Windows clipboard access through the Win32 API
│   └── history.py      Persistent transfer history
└── renderer/
    ├── index.html      Desktop interface
    ├── app.js          Client controller and polling
    └── favicon.png     Application mark
```

## How it runs

`main.py` starts the server, then opens the interface in Microsoft Edge app
mode. If Edge is not installed it falls back to the default browser. Pass
`--no-window` to start the service without opening anything.

The window is Edge, so the app has no native toolkit of its own — the
interface is HTML, CSS and JavaScript served from `renderer/`.

## Where it keeps state

Configuration, transfer history and the log live in `%APPDATA%\Seamless`. The
receiving folder defaults to `Desktop\Seamless Transfer`; an install that still
had the previous `Downloads\Seamless` default is migrated on the next launch,
and a folder the user chose is left untouched.

## The desktop window

`renderer/index.html` and `renderer/app.js` are the interface: device list,
pairing QR code, clipboard toggle, drag-and-drop send zone, live transfer
panel and history. The controller polls `/api/transfer/status` while a
transfer runs and `/api/devices` every three seconds, and redraws the pairing
code every minute so it keeps a valid address and token.
