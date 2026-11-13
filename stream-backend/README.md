# Market Monitor — optional private Alpaca IEX stream

This backend connects once to Alpaca's free IEX trade WebSocket, broadcasts trade updates to authenticated browsers, and does **not** publish Alpaca credentials to GitHub Pages.

## Coverage

Only 30 US stocks/ETFs are subscribed to the IEX feed (see `symbols` in `server.js`). Other heatmap tiles continue using the existing GitHub Actions quote snapshot. IEX is one exchange, not the consolidated market, so some symbols trade infrequently and prices may differ from consolidated quotes. SPX is not an IEX-traded stock and remains on the fallback feed.

## Run

1. Create an Alpaca account and obtain a Market Data API key and secret.
2. Host this folder on a persistent Node.js service with outbound WebSockets and inbound WebSockets (for example, a suitable Render or Railway web service; check current free-tier and sleep restrictions).
3. Set environment variables from `.env.example` **in the hosting service**, not in the public repository. Generate `VIEWER_TOKEN` with `openssl rand -hex 32`. Never commit real credentials.
4. Use `npm install && npm start`. Deploy the service over HTTPS/WSS.
5. On the Market Monitor page, enter your deployed backend URL and viewer token in the connection controls. The token is kept only in the current browser tab session.

## Security and licensing

The backend checks the WebSocket Origin and requires a constant-time-checked viewer token. This is **not** a substitute for a complete identity and access system; a copied token can be used by others. For stronger private access, put the service behind an identity-aware gateway and restrict distribution. **Verify Alpaca's market-data display/redistribution terms before sharing live data on a public website.** The GitHub Pages HTML is public, but its stream remains locked unless a viewer supplies the private token.

No trading endpoints or order placement are implemented. If credentials are absent or the stream fails, the existing delayed `quotes.json` feed remains in use.

## Note

The free plan's historical data access and websocket coverage differ from SIP. The backend uses IEX snapshots for prior-close baselines. Some symbols may have no IEX trade or snapshot; they should remain marked stale/unavailable, not be represented as full-market quotes.
