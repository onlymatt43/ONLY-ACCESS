// server.js - Backend for Zoom Access + Chat System

const express = require("express");
const fs = require("fs");
const path = require("path");
const cors = require("cors");
const http = require("http");
const { Server } = require("socket.io");
const { v4: uuidv4 } = require("uuid");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

app.use(cors({ origin: "*" }));
app.use(express.json());
app.use(express.static("public"));

// File paths
const TOKENS_FILE = path.join(__dirname, "tokens.json");
const SUBSCRIBERS_FILE = path.join(__dirname, "subscribers.json");
const CONFIG_FILE = path.join(__dirname, "config.json");
const BANLIST_FILE = path.join(__dirname, "banlist.json");

// Load helpers
function loadJSON(file) {
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file));
}

function saveJSON(file, data) {
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

function isEmailBanned(email) {
  const banlist = loadJSON(BANLIST_FILE);
  return banlist.includes(email);
}

function isWhitelisted(email) {
  const whitelist = loadJSON(SUBSCRIBERS_FILE);
  return whitelist.includes(email);
}

// POST /generate-token
app.post("/generate-token", (req, res) => {
  const { email } = req.body;
  if (!email || !email.includes("@")) {
    return res.status(400).json({ error: "Invalid email." });
  }

  if (isEmailBanned(email)) {
    return res.status(403).json({ blocked: true });
  }

  const token = uuidv4();
  const tokens = loadJSON(TOKENS_FILE);
  tokens.push({ token, email, used: false });
  saveJSON(TOKENS_FILE, tokens);

  res.json({ token });
});

// GET /access?token=XYZ
app.get("/access", (req, res) => {
  const tokenParam = req.query.token;
  if (!tokenParam) return res.redirect("/ghost.html");

  const tokens = loadJSON(TOKENS_FILE);
  const tokenData = tokens.find(t => t.token === tokenParam);

  if (!tokenData) return res.redirect("/ghost.html");
  if (tokenData.used) return res.redirect("/expired.html");

  tokenData.used = true;
  saveJSON(TOKENS_FILE, tokens);

  const config = loadJSON(CONFIG_FILE);
  const zoomLink = config.currentZoomLink;
  return res.redirect(zoomLink);
});

// GET /current-link
app.get("/current-link", (req, res) => {
  const config = loadJSON(CONFIG_FILE);
  res.json({ zoomLink: config.currentZoomLink });
});

// Socket.IO chat
io.on("connection", socket => {
  console.log("User connected");

  socket.on("message", msg => {
    io.emit("message", msg);
  });

  socket.on("disconnect", () => {
    console.log("User disconnected");
  });
});

// Start server
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
