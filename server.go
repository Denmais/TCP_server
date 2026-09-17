package main

import (
	"fmt"
	"net"
	"strings"
)

func home() string {
	return "home page"
}

func users() string {
	return "users page"
}

func main() {
	listener, err := net.Listen("tcp", "127.0.0.1:8088")
	if err != nil {
		panic(err)
	}
	defer listener.Close()

	fmt.Println("Listening on http://127.0.0.1:8088")

	routes := map[string]func() string{
		"/":      home,
		"/users": users,
	}

	for {
		conn, err := listener.Accept()
		if err != nil {
			fmt.Println("accept error:", err)
			continue
		}

		buffer := make([]byte, 4096)

		n, err := conn.Read(buffer)
		if err != nil {
			conn.Close()
			continue
		}

		data := string(buffer[:n])

		fmt.Println("RAW REQUEST:")
		fmt.Println(data)
		fmt.Println("-------------------------")

		firstLine := strings.Split(data, "\r\n")[0]

		parts := strings.Split(firstLine, " ")

		method := parts[0]
		path := parts[1]
		protocol := parts[2]

		fmt.Println("method:", method)
		fmt.Println("path:", path)
		fmt.Println("protocol:", protocol)

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
			len(body),
			body,
		)

		conn.Write([]byte(response))
		conn.Close()
	}
}
