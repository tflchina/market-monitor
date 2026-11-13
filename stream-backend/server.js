import express from "express";
import WebSocket, { WebSocketServer } from "ws";
import { createServer } from "node:http";
import { timingSafeEqual } from "node:crypto";

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server, path: "/stream" });
const PORT = Number(process.env.PORT || 3000);
const KEY = process.env.ALPACA_API_KEY_ID;
const SECRET = process.env.ALPACA_API_SECRET_KEY;
const VIEWER_TOKEN = process.env.VIEWER_TOKEN;
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || "https://tflchina.github.io";
if (!KEY || !SECRET || !VIEWER_TOKEN) {
  console.error("Set ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY and VIEWER_TOKEN");
  process.exit(1);
}
const symbols = ["CBRS","NVDA","AAPL","MSFT","GOOG","META","AMZN","TSLA","AVGO","AMD","MU","MRVL","INTC","QCOM","ASML","TSM","SNDK","ADBE","ORCL","WDAY","PLTR","NFLX","COST","WMT","DIS","BRK.B","IBKR","SPY","VOO","RDDT"];
const alpacaSymbols = symbols.map(s => s === "BRK.B" ? "BRK.B" : s);
const reverse = Object.fromEntries(symbols.map((s,i) => [alpacaSymbols[i],s]));
const quotes = new Map();
const clients = new Set();
let alpaca;
let reconnectDelay = 1000;
let lastDataAt = null;
const headers = { "APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET };
function validToken(value) {
  if (typeof value !== "string") return false;
  const a = Buffer.from(value), b = Buffer.from(VIEWER_TOKEN);
  return a.length === b.length && timingSafeEqual(a,b);
}
function send(client, payload) {
  if (client.readyState === WebSocket.OPEN) client.send(JSON.stringify(payload));
}
function broadcast(payload) { for (const c of clients) send(c,payload); }
async function initialize() {
  // IEX snapshot includes previous daily bar for change-percent baseline.
  try {
    const url = "https://data.alpaca.markets/v2/stocks/snapshots?feed=iex&symbols=" + encodeURIComponent(alpacaSymbols.join(","));
    const response = await fetch(url, { headers });
    if (!response.ok) throw new Error("Alpaca snapshot HTTP " + response.status);
    const data = await response.json();
    for (const [symbol, snapshot] of Object.entries(data)) {
      const prev = Number(snapshot.previousDailyBar?.c);
      const trade = snapshot.latestTrade;
      const price = Number(trade?.p);
      if (prev > 0 && price > 0) {
        const name = reverse[symbol] || symbol;
        quotes.set(name,{price,changePct:(price / prev - 1)*100,source:"IEX",asOf:trade.t,previousClose:prev});
      }
    }
  } catch (error) { console.error("Snapshot:",error.message); }
}
function connectAlpaca() {
  alpaca = new WebSocket("wss://stream.data.alpaca.markets/v2/iex");
  alpaca.on("open",()=>{ reconnectDelay=1000; });
  alpaca.on("message",raw=>{
    let messages;
    try { messages = JSON.parse(raw.toString()); } catch { return; }
    for(const msg of messages) {
      if(msg.T==="success" && msg.msg==="connected") {
        alpaca.send(JSON.stringify({action:"auth",key:KEY,secret:SECRET}));
      } else if(msg.T==="success" && msg.msg==="authenticated") {
        alpaca.send(JSON.stringify({action:"subscribe",trades:alpacaSymbols}));
      } else if(msg.T==="error") {
        console.error("Alpaca stream error",msg.code,msg.msg);
      } else if(msg.T==="t") {
        const name = reverse[msg.S] || msg.S;
        const price = Number(msg.p);
        if (!(price>0)) continue;
        const old=quotes.get(name);
        const prev=old?.previousClose;
        const update={price,changePct:prev>0?(price/prev-1)*100:null,source:"IEX",asOf:msg.t,previousClose:prev||null};
        quotes.set(name,update);lastDataAt=msg.t;
        broadcast({type:"quote",symbol:name,quote:update});
      }
    }
  });
  alpaca.on("error",error=>console.error("Alpaca stream:",error.message));
  alpaca.on("close",()=>{setTimeout(connectAlpaca,reconnectDelay);reconnectDelay=Math.min(reconnectDelay*2,30000);});
}
app.get("/health",(req,res)=>res.json({ok:true,feed:"IEX",connected:alpaca?.readyState===WebSocket.OPEN,lastDataAt,streamedSymbols:symbols.length}));
wss.on("connection",(client,req)=>{
  if(req.headers.origin!==ALLOWED_ORIGIN) { client.close(1008,"Origin not allowed");return; }
  let authed=false;
  const timeout=setTimeout(()=>{if(!authed)client.close(1008,"Authentication required");},5000);
  client.on("message",raw=>{
    if(authed)return;
    let message;
    try {message=JSON.parse(raw.toString());}catch{return client.close(1008,"Invalid auth");}
    if(message.type!=="auth"||!validToken(message.token))return client.close(1008,"Unauthorized");
    authed=true;clearTimeout(timeout);clients.add(client);
    send(client,{type:"snapshot",quotes:Object.fromEntries(quotes),symbols,feed:"IEX",lastDataAt});
  });
  client.on("close",()=>{clearTimeout(timeout);clients.delete(client);});
});
server.listen(PORT,async()=>{console.log("Market Monitor backend listening on",PORT);await initialize();connectAlpaca();});
