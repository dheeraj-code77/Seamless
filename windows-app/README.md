# Seamless Windows Desktop Application

This directory contains the desktop client for Seamless on Windows.

## Components

- **Frontend (`src/renderer`)**: Implements the approved UI design faithfully (cream background, subtle grain texture, deep forest green title bar, olive moss drop zone, dusty rose accents).
- **Core Server / Network Engine (`src/core`)**: Handles:
  - Local HTTP streaming server on port `5173`.
  - UDP broadcast discovery beacon on port `52400`.
  - Secure PIN generation and verification.
  - Native file saving and progress monitoring.
