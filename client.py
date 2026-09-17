import socket


HOST = "127.0.0.1"
PORT = 8088

path = "/"

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect((HOST, PORT))

request = (
    f"GET {path} HTTP/1.1\r\n"
    f"Host: {HOST}:{PORT}\r\n"
    "Connection: close\r\n"
    "\r\n"
)

client.sendall(request.encode())

response = b""

while True:
    chunk = client.recv(4096)

    if not chunk:
        break

    response += chunk

client.close()

print(response.decode())