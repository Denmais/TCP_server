import asyncio


HOST = "127.0.0.1"
PORT = 8088


def home():
    return "home page"


def users():
    return "users page"


routes = {
    "/": home,
    "/users": users,
}


async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")

    print("connected:", addr)

    data = await reader.read(4096)

    request = data.decode()

    first_line = request.split("\r\n")[0]

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
        "Content-Type: text/plain\r\n"
        f"Content-Length: {len(body.encode())}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{body}"
    )

    writer.write(response.encode())

    await writer.drain()

    writer.close()

    await writer.wait_closed()

    print("closed:", addr)


async def main():
    server = await asyncio.start_server(
        handle_client,
        HOST,
        PORT,
    )

    print(f"Listening on http://{HOST}:{PORT}")

    async with server:
        await server.serve_forever()


asyncio.run(main())