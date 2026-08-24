/**
 * Lark Base ↔ MISA AMIS AI Sync Server
 * Ready for Render.com Deployment (Web Service)
 */

const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve Static Frontend (Simulator & Dashboard)
app.use(express.static(path.join(__dirname)));

// Health Check Endpoint (For Render monitoring)
app.get('/health', (req, res) => {
    res.status(200).json({
        status: 'OK',
        service: 'Lark Base ↔ MISA AMIS AI Sync Middleware',
        timestamp: new Date().toISOString()
    });
});

// Mock Webhook Receiver Endpoint (Ready for Lark Open Platform)
app.post('/api/webhook/lark', (req, res) => {
    console.log('[Webhook Received from Lark]:', req.body);
    res.status(200).json({
        code: 0,
        msg: 'Webhook received successfully',
        data: {
            processed_at: new Date().toISOString()
        }
    });
});

// Fallback to index.html for SPA routing
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Start Server
app.listen(PORT, () => {
    console.log(`=================================================`);
    console.log(`🚀 Lark ↔ MISA AI Sync Server is running!`);
    console.log(`🌐 Local URL: http://localhost:${PORT}`);
    console.log(`☁️  Port: ${PORT}`);
    console.log(`=================================================`);
});
