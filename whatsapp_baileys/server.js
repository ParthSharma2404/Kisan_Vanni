import express from 'express';
import cors from 'cors';
import pino from 'pino';
import QRCode from 'qrcode';
import {
  makeWASocket,
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion
} from '@whiskeysockets/baileys';

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 5005;
const DEFAULT_FARMER_PHONE = "";

let sock = null;
let latestQR = null;
let connectionStatus = "disconnected"; // "disconnected" | "connecting" | "connected"
let pairedNumber = null;

async function startWhatsAppBot() {
  try {
    const { state, saveCreds } = await useMultiFileAuthState('./baileys_auth_info');
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
      version,
      auth: state,
      logger: pino({ level: 'silent' }),
      browser: ['Kisan-Vaani', 'Chrome', '1.0.0']
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        latestQR = qr;
        if (connectionStatus !== "waiting_for_qr_scan") {
          connectionStatus = "waiting_for_qr_scan";
          console.log(`[Baileys] 📲 WhatsApp Web QR code ready. Available via /api/whatsapp/qr or in UI modal.`);
        }
      }

      if (connection === 'close') {
        const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
        console.log(`[Baileys] Connection closed. Reconnecting: ${shouldReconnect}`);
        connectionStatus = "disconnected";
        latestQR = null;
        if (shouldReconnect) {
          startWhatsAppBot();
        }
      } else if (connection === 'open') {
        connectionStatus = "connected";
        latestQR = null;
        console.log(`[Baileys] ✅ WhatsApp successfully connected and ready to send farmer advisories!`);
      }
    });

  } catch (err) {
    console.error(`[Baileys] Initialization error:`, err);
  }
}

// 1. Connection Status Endpoint
app.get('/api/whatsapp/status', (req, res) => {
  res.json({
    status: connectionStatus,
    target_phone: DEFAULT_FARMER_PHONE,
    has_qr: Boolean(latestQR)
  });
});

// 2. QR Code as DataURL / HTML Image
app.get('/api/whatsapp/qr', async (req, res) => {
  if (connectionStatus === 'connected') {
    return res.json({ connected: true, message: "WhatsApp is already connected!" });
  }
  if (!latestQR) {
    return res.json({ connected: false, message: "Generating QR code, please refresh in 2 seconds..." });
  }
  try {
    const qrDataUrl = await QRCode.toDataURL(latestQR);
    res.json({ connected: false, qr_data_url: qrDataUrl });
  } catch (err) {
    res.status(500).json({ error: "Failed to generate QR image" });
  }
});

// 3. Send Advisory to Farmer Phone (Default: 7985397373)
app.post('/api/whatsapp/send', async (req, res) => {
  const { phone = DEFAULT_FARMER_PHONE, message } = req.body;
  if (!message) {
    return res.status(400).json({ error: "message is required" });
  }

  // Format phone number to WhatsApp JID: 917985397373@s.whatsapp.net
  let cleanPhone = phone.replace(/[^0-9]/g, '');
  if (cleanPhone.length === 10) {
    cleanPhone = '91' + cleanPhone;
  }
  const jid = `${cleanPhone}@s.whatsapp.net`;

  if (connectionStatus !== 'connected' || !sock) {
    return res.status(503).json({
      success: false,
      status: connectionStatus,
      error: "WhatsApp Baileys is not linked yet. Scan QR code first.",
      fallback_whatsapp_link: `https://api.whatsapp.com/send?phone=${cleanPhone}&text=${encodeURIComponent(message)}`
    });
  }

  try {
    const result = await sock.sendMessage(jid, { text: message });
    console.log(`[Baileys] 📨 Advisory successfully delivered to ${cleanPhone}!`);
    return res.json({
      success: true,
      delivered_to: cleanPhone,
      message_id: result?.key?.id
    });
  } catch (err) {
    console.error(`[Baileys] Error sending message:`, err);
    return res.status(500).json({
      success: false,
      error: err.message,
      fallback_whatsapp_link: `https://api.whatsapp.com/send?phone=${cleanPhone}&text=${encodeURIComponent(message)}`
    });
  }
});

app.listen(PORT, () => {
  console.log(`[Baileys Service] Running on http://localhost:${PORT}`);
  startWhatsAppBot();
});
