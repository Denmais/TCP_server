import socket
import threading
import time


HOST = "127.0.0.1"
PORT = 8088


def home():
    time.sleep(10)
    return "home page"


def users():
    return "users page"


routes = {
    "/": home,
    "/users": users,
}


def handle_client(conn, addr):
    print("connected:", addr)

    try:
        data = conn.recv(4096).decode()

        first_line = data.split("\r\n")[0]

        method, path, protocol = first_line.split()

        print(addr, method, path)

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

    finally:
        conn.close()
        print("closed:", addr)


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()

print(f"Listening on http://{HOST}:{PORT}")

while True:
    conn, addr = server.accept()

    thread = threading.Thread(
        target=handle_client,
        args=(conn, addr),
    )

    thread.start()