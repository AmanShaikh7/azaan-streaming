"""
Azaan Live Streaming - Server-Based Audio Streaming (No WebRTC)
Audio flows through the server instead of P2P

Install: pip install flask flask-socketio flask-cors simple-websocket
Run: python server.py
"""

from flask import Flask, request, send_from_directory, render_template_string
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import os
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'azaan-secret-key-2024'
CORS(app)

# Use threading mode for compatibility
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1000000  # 1MB for audio chunks
)

# Store active broadcasts {masjid_id: broadcaster_socket_id}
active_broadcasts = {}
# Store listener counts
listener_counts = {}

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Azaan Streaming Server</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                text-align: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 { color: #333; margin-bottom: 20px; }
            .status { 
                background: #10b981;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                display: inline-block;
                margin: 20px 0;
                font-weight: 600;
            }
            .link-box {
                background: #f3f4f6;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }
            a {
                display: block;
                background: #3b82f6;
                color: white;
                padding: 15px;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px 0;
                font-weight: 600;
                transition: background 0.3s;
            }
            a:hover { background: #2563eb; }
            .info { 
                background: #dbeafe;
                padding: 15px;
                border-radius: 8px;
                margin-top: 20px;
                color: #1e40af;
                font-size: 14px;
            }
            code {
                background: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-family: monospace;
            }
            .stat {
                background: #f0f0f0;
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🕌 Azaan Streaming Server</h1>
            <div class="status">✅ Server is Running</div>
            <div class="stat">
                <strong>Streaming Mode:</strong> Server-Based (No P2P)<br>
                <strong>Active Broadcasts:</strong> {{ active_count }}<br>
                <strong>Architecture:</strong> Audio flows through server
            </div>
            
            <div class="link-box">
                <h3 style="margin-top: 0;">Access Pages:</h3>
                <a href="/broadcaster">📡 Broadcaster Page (For Masjid)</a>
                <a href="/listener">🔊 Listener Page (For Users)</a>
            </div>
            
            <div class="info">
                <strong>📌 Server URL:</strong><br>
                <code>{{ server_url }}</code><br>
                <small>Works on all networks - no TURN needed!</small>
            </div>
        </div>
    </body>
    </html>
    """, active_count=len(active_broadcasts), server_url=request.url_root.rstrip('/'))

@app.route('/broadcaster')
def broadcaster():
    try:
        return send_from_directory('.', 'broadcaster.html')
    except:
        return """
        <html><body style='font-family: Arial; padding: 50px; text-align: center;'>
        <h1>⚠️ broadcaster.html not found</h1>
        <p>Please add broadcaster.html to your repository root.</p>
        </body></html>
        """

@app.route('/listener')
def listener():
    try:
        return send_from_directory('.', 'listener.html')
    except:
        return """
        <html><body style='font-family: Arial; padding: 50px; text-align: center;'>
        <h1>⚠️ listener.html not found</h1>
        <p>Please add listener.html to your repository root.</p>
        </body></html>
        """

@app.route('/health')
def health():
    return {
        "status": "ok", 
        "active_broadcasts": len(active_broadcasts),
        "streaming_mode": "server-based",
        "async_mode": socketio.async_mode
    }

@app.route('/active-broadcasts')
def get_active_broadcasts():
    return {
        "broadcasts": list(active_broadcasts.keys()), 
        "count": len(active_broadcasts)
    }

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connected', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    
    # Clean up if broadcaster disconnects
    masjids_to_remove = []
    for masjid_id, broadcaster_id in active_broadcasts.items():
        if broadcaster_id == request.sid:
            masjids_to_remove.append(masjid_id)
            emit('broadcast-stopped', room=f'masjid-{masjid_id}')
    
    for masjid_id in masjids_to_remove:
        del active_broadcasts[masjid_id]
        if masjid_id in listener_counts:
            del listener_counts[masjid_id]
        print(f'Removed broadcast for masjid: {masjid_id}')

@socketio.on('start-broadcast')
def handle_start_broadcast(data):
    masjid_id = data.get('masjidId')
    
    if not masjid_id:
        emit('error', {'message': 'Masjid ID required'})
        return
    
    active_broadcasts[masjid_id] = request.sid
    listener_counts[masjid_id] = 0
    join_room(f'masjid-{masjid_id}')
    
    print(f'Broadcast started for masjid: {masjid_id} by {request.sid}')
    
    emit('broadcast-started', {'masjidId': masjid_id}, broadcast=True)
    emit('broadcast-status', {'status': 'live', 'masjidId': masjid_id})

@socketio.on('stop-broadcast')
def handle_stop_broadcast(data):
    masjid_id = data.get('masjidId')
    
    if masjid_id in active_broadcasts:
        del active_broadcasts[masjid_id]
        if masjid_id in listener_counts:
            del listener_counts[masjid_id]
        emit('broadcast-stopped', room=f'masjid-{masjid_id}')
        print(f'Broadcast stopped for masjid: {masjid_id}')

@socketio.on('join-broadcast')
def handle_join_broadcast(data):
    masjid_id = data.get('masjidId')
    
    if not masjid_id:
        emit('error', {'message': 'Masjid ID required'})
        return
    
    join_room(f'masjid-{masjid_id}')
    
    broadcaster_id = active_broadcasts.get(masjid_id)
    
    if broadcaster_id:
        # Update listener count
        listener_counts[masjid_id] = listener_counts.get(masjid_id, 0) + 1
        
        print(f'Listener {request.sid} joined masjid: {masjid_id}')
        
        # Tell broadcaster about listener count
        emit('listener-count', {
            'count': listener_counts[masjid_id]
        }, room=broadcaster_id)
        
        emit('joined-broadcast', {'masjidId': masjid_id, 'success': True})
    else:
        emit('error', {'message': 'Broadcast not active for this masjid'})

@socketio.on('leave-broadcast')
def handle_leave_broadcast(data):
    masjid_id = data.get('masjidId')
    if masjid_id:
        leave_room(f'masjid-{masjid_id}')
        
        # Update listener count
        if masjid_id in listener_counts and listener_counts[masjid_id] > 0:
            listener_counts[masjid_id] -= 1
            
            # Notify broadcaster
            broadcaster_id = active_broadcasts.get(masjid_id)
            if broadcaster_id:
                emit('listener-count', {
                    'count': listener_counts[masjid_id]
                }, room=broadcaster_id)
        
        print(f'Listener {request.sid} left masjid: {masjid_id}')

# NEW: Audio streaming through server
@socketio.on('audio-data')
def handle_audio_data(data):
    """
    Broadcaster sends audio chunks, server broadcasts to all listeners
    """
    masjid_id = data.get('masjidId')
    audio_chunk = data.get('audio')
    
    if masjid_id and audio_chunk:
        # Broadcast audio to all listeners in this room
        emit('audio-stream', {
            'audio': audio_chunk,
            'timestamp': data.get('timestamp', 0)
        }, room=f'masjid-{masjid_id}', include_self=False)

if __name__ == '__main__':
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    print("="*50)
    print("🕌 Azaan Streaming Server Starting...")
    print(f"Port: {port}")
    print("Mode: Server-Based Audio Streaming (No WebRTC)")
    print(f"Async Mode: {socketio.async_mode}")
    print("="*50)
    
    # Run with socketio
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=port, 
        debug=False,
        allow_unsafe_werkzeug=True
    )