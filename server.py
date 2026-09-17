import socket


HOST = "127.0.0.1"
PORT = 8088


def home():
    return "home page"


def users():
    return "USERS:..."


routes = {
    "/": home,
    "/users": users,
}


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

print(f"http://{HOST}:{PORT}")

while True:
    conn, addr = server.accept()

    data = conn.recv(4096).decode()
    print(data)

    first_line = data.split("\r\n")[0]

    method, path, protocol = first_line.split()

    print("method:", method)
    print("path:", path)
    print("protocol", protocol)

    handler = routes.get(path)

    if handler:
        body = handler()
        status = "200 OK"
    else:
        body = "404 not found"
        status = "404 Not Found"

    response = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body.encode())}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{body}"
    )

    conn.sendall(response.encode())
    conn.close()