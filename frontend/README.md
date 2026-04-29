# frontend

Vite + React + TypeScript + Ketcher (standalone).

## Setup

```sh
npm install
npm run dev
```

The Ketcher canvas runs entirely in-browser via `ketcher-standalone` — no remote chem service required. Backend wiring (the `/plan` button, the chat) lives off `http://localhost:8123` by default; see `backend/README.md`.

## Build

```sh
npm run build
```

The bundle is large (~24MB unminified, ~7MB gzipped) because Ketcher ships a full chemistry engine. Code-splitting is v2 territory.
