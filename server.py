"""
Azaan Live Streaming - Python WebRTC Signaling Server
Install: pip install flask flask-socketio flask-cors eventlet
Run: python server.py
"""

from flask import Flask, request, send_from_directory, render_template_string
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'azaan-secret-key-2024'
CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', logger=True, engineio_logger=False)

# Store active broadcasts {masjid_id: broadcaster_socket_id}
active_broadcasts = {}

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Azaan Streaming Server</title>
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
            }
            a:hover { background: #2563eb; }
            .info { 
                background: #dbeafe;
                padding: 15px;
                border-radius: 8px;
                margin-top: 20px;
                color: #1e40af;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🕌 Azaan Streaming Server</h1>
            <div class="status">✅ Server is Running</div>
            <p>Active Broadcasts: <strong>{{ active_count }}</strong></p>
            
            <div class="link-box">
                <h3>Access Pages:</h3>
                <a href="/broadcaster">📡 Broadcaster Page (For Masjid)</a>
                <a href="/listener">🔊 Listener Page (For Users)</a>
            </div>
            
            <div class="info">
                <strong>Server URL:</strong><br>
                <code style="background: white; padding: 5px 10px; border-radius: 4px;">
                    {{ server_url }}
                </code>
            </div>
        </div>
    </body>
    </html>
    """, active_count=len(active_broadcasts), server_url=request.url_root)

@app.route('/broadcaster')
def broadcaster():
    try:
        return send_from_directory('.', 'broadcaster.html')
    except:
        return "broadcaster.html not found. Please add it to the repository."

@app.route('/listener')
def listener():
    try:
        return send_from_directory('.', 'listener.html')
    except:
        return "listener.html not found. Please add it to the repository."

@app.route('/active-broadcasts')
def get_active_broadcasts():
    return {"broadcasts": list(active_broadcasts.keys()), "count": len(active_broadcasts)}

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connected', {'sid': request.sid})

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

@socketio.on('start-broadcast')
def handle_start_broadcast(data):
    masjid_id = data.get('masjidId')
    
    if not masjid_id:
        emit('error', {'message': 'Masjid ID required'})
        return
    
    active_broadcasts[masjid_id] = request.sid
    join_room(f'masjid-{masjid_id}')
    
    print(f'Broadcast started for masjid: {masjid_id}')
    
    # Notify all clients that broadcast started
    emit('broadcast-started', {'masjidId': masjid_id}, broadcast=True)
    emit('broadcast-status', {'status': 'live', 'masjidId': masjid_id})

@socketio.on('stop-broadcast')
def handle_stop_broadcast(data):
    masjid_id = data.get('masjidId')
    
    if masjid_id in active_broadcasts:
        del active_broadcasts[masjid_id]
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
        print(f'Listener {request.sid} joined masjid: {masjid_id}')
        
        # Tell broadcaster about new listener
        emit('listener-joined', {
            'listenerId': request.sid
        }, room=broadcaster_id)
        
        emit('joined-broadcast', {'masjidId': masjid_id})
    else:
        emit('error', {'message': 'Broadcast not active'})

@socketio.on('leave-broadcast')
def handle_leave_broadcast(data):
    masjid_id = data.get('masjidId')
    if masjid_id:
        leave_room(f'masjid-{masjid_id}')
        print(f'Listener {request.sid} left masjid: {masjid_id}')

# WebRTC Signaling Messages
@socketio.on('offer')
def handle_offer(data):
    to_sid = data.get('to')
    offer = data.get('offer')
    
    if to_sid and offer:
        emit('offer', {
            'from': request.sid,
            'offer': offer
        }, room=to_sid)

@socketio.on('answer')
def handle_answer(data):
    to_sid = data.get('to')
    answer = data.get('answer')
    
    if to_sid and answer:
        emit('answer', {
            'from': request.sid,
            'answer': answer
        }, room=to_sid)

@socketio.on('ice-candidate')
def handle_ice_candidate(data):
    to_sid = data.get('to')
    candidate = data.get('candidate')
    
    if to_sid and candidate:
        emit('ice-candidate', {
            'from': request.sid,
            'candidate': candidate
        }, room=to_sid)

if __name__ == '__main__':
    print("="*50)
    print("🕌 Azaan Streaming Server Starting...")
    print("Server will run on: http://localhost:5000")
    print("="*50)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)