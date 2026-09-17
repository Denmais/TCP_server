# Mini TCP/HTTP Server in Go

Схема проекта:

```text
TCP -> HTTP -> Router -> Handler -> HTTP Response -> TCP
```

## Структура

```text
mini-http/
├── server.go
└── README.md
```

## 1. Запуск сервера

```bash
go run server.go
```

Сервер слушает:

```text
127.0.0.1:8080
```

```go
listener, err := net.Listen("tcp", "127.0.0.1:8080")
```

Схема:

```text
server.go
   |
   v
net.Listen(...)
   |
   v
TCP listening socket
   |
   v
127.0.0.1:8080
```

`listener` принимает новые TCP-соединения:

```go
conn, err := listener.Accept()
```

---

## 2. Подключение пользователя

Пользователь открывает:

```text
http://127.0.0.1:8080/users
```

Браузер создаёт TCP-соединение:

```text
User / Browser
      |
      | TCP connect
      v
127.0.0.1:8080
      |
      v
listener.Accept()
      |
      v
    conn
```

`conn` — TCP-соединение с конкретным клиентом.

---

## 3. HTTP внутри TCP

Браузер формирует HTTP-запрос:

```http
GET /users HTTP/1.1
Host: 127.0.0.1:8080
User-Agent: Mozilla/5.0 ...
Accept: text/html
Connection: keep-alive
```

HTTP передаётся через TCP как последовательность байтов:

```text
Browser
   |
   | TCP connection
   |
   | bytes
   v
Server
```

TCP не знает про:

```text
GET
POST
/users
headers
JSON
status codes
```

Для TCP это только поток байтов.

---

## 4. Чтение данных

```go
buffer := make([]byte, 4096)

n, err := conn.Read(buffer)
```

`buffer` — массив байтов.

Например начало запроса:

```text
index       byte       symbol

buffer[0]    71          G
buffer[1]    69          E
buffer[2]    84          T
buffer[3]    32        space
buffer[4]    47          /
```

`n` — количество байтов, реально прочитанных этим вызовом `Read`.

```go
data := string(buffer[:n])
```

Преобразует полученные байты в строку:

```text
GET /users HTTP/1.1
Host: 127.0.0.1:8080
...
```

---

## 5. Разбор HTTP request line

Первая строка:

```text
GET /users HTTP/1.1
```

Разбор:

```go
firstLine := strings.Split(data, "\r\n")[0]
parts := strings.Split(firstLine, " ")

method := parts[0]
path := parts[1]
protocol := parts[2]
```

Результат:

```text
method   = GET
path     = /users
protocol = HTTP/1.1
```

---

## 6. Router

```go
routes := map[string]func() string{
    "/":      home,
    "/users": users,
}
```

По `path` выбирается handler:

```go
handler, exists := routes[path]
```

Схема:

```text
GET /users HTTP/1.1
        |
        v
 path = "/users"
        |
        v
      router
        |
        v
 routes["/users"]
        |
        v
     users()
```

---

## 7. Handler

```go
func users() string {
    return "users page"
}
```

Handler возвращает данные для ответа:

```text
users()
   |
   v
"users page"
```

---

## 8. HTTP response

Сервер формирует ответ:

```http
HTTP/1.1 200 OK
Content-Type: text/plain
Content-Length: 10
Connection: close

users page
```

Отправка:

```go
conn.Write([]byte(response))
```

Схема:

```text
handler
   |
   v
response string
   |
   v
[]byte
   |
   v
conn.Write(...)
   |
   | TCP
   v
Browser
```

---

# Два пользователя

Пользователи подключаются в разное время и выполняют действия последовательно.

## Пользователь A

Открывает:

```text
/
```

```text
User A
  |
  | TCP A
  v
Accept()
  |
  v
GET /
  |
  v
router
  |
  v
home()
  |
  v
200 OK
  |
  v
conn.Close()
```

---

## Пользователь B

После этого пользователь B открывает:

```text
/users
```

```text
User B
  |
  | TCP B
  v
Accept()
  |
  v
GET /users
  |
  v
router
  |
  v
users()
  |
  v
200 OK
  |
  v
conn.Close()
```

---

## Пользователь A делает ещё один запрос

Позже пользователь A открывает:

```text
/users
```

Если предыдущее TCP-соединение было закрыто, создаётся новое:

```text
User A
   |
   +---- TCP A ---- GET /
   |
   +---- TCP C ---- GET /users

User B
   |
   +---- TCP B ---- GET /users
```

Один пользователь не равен одному TCP-соединению.

---

# Последовательная обработка

При таком коде:

```go
for {
    conn, _ := listener.Accept()

    // read
    // parse HTTP
    // route
    // handler
    // response

    conn.Close()
}
```

сервер обрабатывает соединения последовательно.

```text
time ------------------------------------------------------>

User A:
    connect
       |
       +------ request A ------+
                               |
                            response

Server:
    Accept A
       |
       read
       |
       parse
       |
       route
       |
       handler
       |
       response
       |
       close A
                               |
                               +---- Accept B

User B:
                               connect
                                  |
                                  +---- request B ----+
```

Следующее TCP-соединение может ждать в очереди, пока сервер занят текущим.

---

# POST больше 4096 байт

```go
buffer := make([]byte, 4096)
```

`4096` — размер одного буфера чтения.

Он не ограничивает размер HTTP-запроса.

Например:

```http
POST /users HTTP/1.1
Content-Length: 10000

<10000 bytes body>
```

Данные могут быть прочитаны частями:

```text
TCP stream

[ 4096 bytes ]
       |
       v
    Read #1

[ 4096 bytes ]
       |
       v
    Read #2

[ remaining bytes ]
       |
       v
    Read #3
```

Один `Read()` может вернуть любое количество доступных байтов:

```text
120
700
4096
38
...
```

Границы `Read()` не совпадают с границами HTTP-запроса.

---

# Чтение полного HTTP-запроса

Сначала нужно найти конец headers:

```text
\r\n\r\n
```

Пример:

```http
POST /users HTTP/1.1
Host: localhost
Content-Type: application/json
Content-Length: 16

{"name":"Alex"}
```

Схема:

```text
POST /users HTTP/1.1\r\n
Host: localhost\r\n
Content-Type: application/json\r\n
Content-Length: 16\r\n
\r\n
{"name":"Alex"}
|-----------------------------------------------|
                    headers

                                                |--------------|
                                                      body
```

Алгоритм:

```text
1. Читать TCP
        |
        v
2. Накапливать bytes
        |
        v
3. Найти \r\n\r\n
        |
        v
4. Распарсить headers
        |
        v
5. Прочитать Content-Length
        |
        v
6. Дочитать body до нужной длины
        |
        v
7. Передать request router'у
```

---

# Общая схема

```text
                   USER A                 USER B
                  Browser                Browser
                     |                      |
                     | TCP                  | TCP
                     |                      |
                     +----------+-----------+
                                |
                                v
                     +--------------------+
                     |   TCP LISTENER     |
                     |  127.0.0.1:8080    |
                     +--------------------+
                                |
                         listener.Accept()
                                |
                                v
                     +--------------------+
                     | TCP CONNECTION     |
                     |       conn         |
                     +--------------------+
                                |
                           conn.Read()
                                |
                                v
                     +--------------------+
                     |     RAW BYTES      |
                     +--------------------+
                                |
                                v
                     +--------------------+
                     |    HTTP PARSER     |
                     |                    |
                     | method = GET       |
                     | path = /users      |
                     +--------------------+
                                |
                                v
                     +--------------------+
                     |      ROUTER        |
                     |                    |
                     | "/"      -> home   |
                     | "/users" -> users  |
                     +--------------------+
                                |
                                v
                     +--------------------+
                     |      HANDLER       |
                     |      users()       |
                     +--------------------+
                                |
                                v
                     +--------------------+
                     |   HTTP RESPONSE    |
                     |      200 OK        |
                     +--------------------+
                                |
                           conn.Write()
                                |
                                v
                              TCP
                                |
                                v
                             Browser
```

---

# Слои

```text
Application
    |
    | Router
    | Handler
    |
    v
HTTP
    |
    | request / response format
    |
    v
TCP
    |
    | byte stream
    |
    v
Operating System
```

Коротко:

```text
TCP       = соединение + передача байтов
HTTP      = формат request/response
Router    = выбор handler по path
Handler   = код, который обрабатывает запрос
```
