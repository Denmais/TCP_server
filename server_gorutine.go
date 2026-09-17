package main

import (
	"fmt"
	"net"
	"strings"
	"time"
)

func home() string {
	time.Sleep(10 * time.Second)
	return "home page"
}

func users() string {
	return "users page"
}

var routes = map[string]func() string{
	"/":      home,
	"/users": users,
}

func handleClient(conn net.Conn) {
	defer conn.Close()

	addr := conn.RemoteAddr()

	fmt.Println("connected:", addr)

	buffer := make([]byte, 4096)

	n, err := conn.Read(buffer)
	if err != nil {
		fmt.Println("read error:", err)
		return
	}

	data := string(buffer[:n])

	firstLine := strings.Split(data, "\r\n")[0]
	parts := strings.Split(firstLine, " ")

	if len(parts) != 3 {
		return
	}

	method := parts[0]
	path := parts[1]
	protocol := parts[2]

	fmt.Println(addr, method, path, protocol)

	handler, exists := routes[path]

	var body string
	var status string

	if exists {
		body = handler()
		status = "200 OK"
	} else {
		body = "404 not found"
		status = "404 Not Found"
	}

	response := fmt.Sprintf(
		"HTTP/1.1 %s\r\n"+
			"Content-Type: text/plain; charset=utf-8\r\n"+
			"Content-Length: %d\r\n"+
			"Connection: close\r\n"+
			"\r\n"+
			"%s",
		status,
		len([]byte(body)),
		body,
	)

	_, err = conn.Write([]byte(response))
	if err != nil {
		fmt.Println("write error:", err)
		return
	}

	fmt.Println("closed:", addr)
}

func main() {
	listener, err := net.Listen("tcp", "127.0.0.1:8088")
	if err != nil {
		panic(err)
	}

	defer listener.Close()

	fmt.Println("Listening on http://127.0.0.1:8088")

	for {
		conn, err := listener.Accept()
		if err != nil {
			fmt.Println("accept error:", err)
			continue
		}

		go handleClient(conn)
	}
}
