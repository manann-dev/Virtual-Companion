from flask import Flask
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return 'Hello, SocketIO!'

if __name__ == '__main__':
    socketio.run(app)
