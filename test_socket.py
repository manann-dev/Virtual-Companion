import websocket

try:
    ws = websocket.WebSocket()
    ws.connect("ws://0.0.0.0:5000/test?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcxNDEzODYxOCwianRpIjoiODM0NWU1NTktOTYxMC00ZjI2LWEyM2UtN2MxZDc1YWMyMWRlIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6eyJ1c2VybmFtZSI6InRlc3QxIn0sIm5iZiI6MTcxNDEzODYxOCwiY3NyZiI6ImVlMDVlMTZjLTg4NzItNGU1OS1iMjFmLTRkMjlmZTNkNDNiOSIsImV4cCI6MTcxNDEzOTUxOH0.V_v4jpzmL2w8Tq2Yr6v4EVo-vVYrxZtlZnSvbrpI-z8")
    print("Connected")
    ws.send("Hello, Server!")
    print("Sent")
    print("Receiving...")
    result = ws.recv()
    print("Received '%s'" % result)
    ws.close()
except Exception as e:
    print(e)
