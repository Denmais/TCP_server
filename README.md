# Mini TCP/HTTP Server in Go

Учебный проект, чтобы понять связь:

```text
TCP -> HTTP -> Router -> Handler -> HTTP Response -> TCP
```

Без `net/http`: TCP-соединения и HTTP-запросы разбираются вручную.

---

## Структура проекта

```text
mini-http/
├── server.go
└── README.md
```

---

## 1. Запуск сервера

```bash
go run server.go
```

Сервер начинает слушать:

```text
127.0.0.1:8080
```

В коде:

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

`listener` пока не является соединением с конкретным пользователем.

Он только ждёт новые TCP-соединения.

---

## 2. Подключается пользователь A

Пользователь A открывает:

```text
http://127.0.0.1:8080/
```

Браузер создаёт TCP-соединение с сервером:

```text
User A / Firefox
       |
       | TCP connect
       v
127.0.0.1:8080
       |
       v
listener.Accept()
       |
       v
     conn A
```

Сервер получает конкретное соединение:

```go
conn, err := listener.Accept()
```

`conn` теперь представляет TCP-соединение с пользователем A.

---

## 3. Пользователь A отправляет HTTP-запрос

Firefox формирует HTTP-запрос примерно такого вида:

```http
GET / HTTP/1.1
Host: 127.0.0.1:8080
User-Agent: Mozilla/5.0 ...
Accept: text/html
Connection: keep-alive
```

HTTP здесь — просто данные внутри TCP.

```text
User A
  |
  | TCP connection A
  |
  | bytes:
  |
  | GET / HTTP/1.1
  | Host: ...
  | Accept: ...
  v
server
```

Сервер читает эти байты:

```go
buffer := make([]byte, 4096)

n, err := conn.Read(buffer)
```

Например начало `buffer` может выглядеть так:

```text
index       byte        symbol

buffer[0]    71           G
buffer[1]    69           E
buffer[2]    84           T
buffer[3]    32          space
buffer[4]    47           /
```

После:

```go
data := string(buffer[:n])
```

получаем строку:

```text
GET / HTTP/1.1
Host: 127.0.0.1:8080
...
```

---

## 4. HTTP parser

Первая строка запроса:

```text
GET / HTTP/1.1
```

Мы разбираем её:

```go
firstLine := strings.Split(data, "\r\n")[0]

parts := strings.Split(firstLine, " ")

method := parts[0]
path := parts[1]
protocol := parts[2]
```

Получаем:

```text
method   = GET
path     = /
protocol = HTTP/1.1
```

---

## 5. Router

Наш router:

```go
routes := map[string]func() string{
    "/":      home,
    "/users": users,
}
```

Для запроса:

```text
GET /users HTTP/1.1
```

получаем:

```go
handler, exists := routes["/users"]
```

и вызываем:

```go
body := handler()
```

То есть:

```text
HTTP request

GET /users HTTP/1.1
        |
        v
   path="/users"
        |
        v
      router
        |
        v
 routes["/users"]
        |
        v
     users()
        |
        v
  "users page"
```

---

## 6. HTTP response

Handler возвращает данные:

```go
func users() string {
    return "users page"
}
```

Сервер формирует HTTP response:

```http
HTTP/1.1 200 OK
Content-Type: text/plain
Content-Length: 10
Connection: close

users page
```

И отправляет его через то же TCP-соединение:

```go
conn.Write([]byte(response))
```

Схема:

```text
users()
   |
   v
"users page"
   |
   v
HTTP response
   |
   v
[]byte
   |
   v
conn.Write(...)
   |
   | TCP connection A
   v
Firefox
```

---

# Два пользователя

Теперь пусть есть два пользователя.

Они пришли не одновременно.

## Шаг 1 — пользователь A

В 12:00 пользователь A открывает:

```text
/
```

Происходит:

```text
User A
  |
  | TCP connection A
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
```

После ответа наш учебный сервер делает:

```go
conn.Close()
```

TCP connection A закрыт.

---

## Шаг 2 — пользователь B

Через несколько секунд пользователь B открывает:

```text
/users
```

Создаётся уже другое TCP-соединение:

```text
User B
  |
  | TCP connection B
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
```

---

## Шаг 3 — пользователь A делает ещё одно действие

Теперь пользователь A нажимает ссылку:

```text
/users
```

Если предыдущее соединение было закрыто, браузер создаёт новое:

```text
User A
  |
  | TCP connection C
  v
Accept()
  |
  v
GET /users
```

То есть один пользователь не обязательно равен одному TCP connection.

```text
User A
   |
   +---- TCP A ---- GET /
   |
   +---- TCP C ---- GET /users
```

А другой пользователь:

```text
User B
   |
   +---- TCP B ---- GET /users
```

---

# Последовательная работа нашего сервера

Сейчас сервер однопоточный:

```go
for {
    conn, _ := listener.Accept()

    // обработка запроса

    conn.Close()
}
```

Поэтому порядок примерно такой:

```text
time ---------------------------------------------------->

User A:
    connect
       |
       +------ GET / ------+
                         response

Server:
    Accept A
       |
       read
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
                            +---- GET /users ----+
                                             response
```

Пока сервер обрабатывает A, следующий connection может ждать в очереди TCP.

После завершения A сервер снова вызывает:

```go
listener.Accept()
```

и получает следующий connection.

---

# Где TCP, а где HTTP

```text
+---------------------------------------------------+
|                    APPLICATION                    |
|                                                   |
|     Router -> Handler -> Application logic        |
+---------------------------------------------------+

                        ^
                        |
                    HTTP request
                    HTTP response
                        |
                        v

+---------------------------------------------------+
|                       HTTP                        |
|                                                   |
|   GET /users HTTP/1.1                             |
|   Host: ...                                       |
|   Content-Length: ...                             |
|                                                   |
|   HTTP/1.1 200 OK                                 |
|   Content-Type: ...                               |
+---------------------------------------------------+

                        ^
                        |
                  stream of bytes
                        |
                        v

+---------------------------------------------------+
|                       TCP                         |
|                                                   |
|     connection A                                  |
|     connection B                                  |
|     connection C                                  |
+---------------------------------------------------+

                        ^
                        |
                        v

                    Operating System
```

TCP не знает ничего про:

```text
GET
POST
/users
headers
JSON
HTTP status
```

Для TCP всё это просто байты.

---

# Что если POST больше 4096 байт?

Вот это:

```go
buffer := make([]byte, 4096)

n, err := conn.Read(buffer)
```

означает:

> прочитать максимум 4096 байт за один вызов `Read`.

Это НЕ означает:

> весь HTTP request обязательно поместится в 4096 байт.

Например клиент отправляет:

```http
POST /users HTTP/1.1
Content-Length: 10000

<10000 bytes>
```

TCP может доставить данные частями:

```text
HTTP request = 10000+ bytes

TCP stream:

[ chunk 1 ]
4096 bytes

[ chunk 2 ]
4096 bytes

[ chunk 3 ]
remaining bytes
```

Тогда сервер должен читать несколько раз:

```text
conn.Read()
    |
    +---- 4096 bytes

conn.Read()
    |
    +---- 4096 bytes

conn.Read()
    |
    +---- remaining bytes
```

---

## Важный момент

Нельзя считать, что:

```go
conn.Read(buffer)
```

вернёт ровно 4096 байт.

Он может вернуть:

```text
120 bytes
700 bytes
4096 bytes
38 bytes
...
```

TCP — поток байтов.

Границы одного `Read()` не совпадают с границами HTTP request.

---

# Как понять, сколько читать

Для обычного HTTP request сначала читаются headers.

Они заканчиваются:

```text
\r\n\r\n
```

Например:

```http
POST /users HTTP/1.1
Host: localhost
Content-Type: application/json
Content-Length: 18

{"name":"Alice"}
```

После headers сервер видит:

```text
Content-Length: 18
```

Это означает:

> после headers нужно получить ещё 18 байт body.

Схема:

```text
TCP stream
    |
    v

POST /users HTTP/1.1\r\n
Host: localhost\r\n
Content-Length: 18\r\n
\r\n
{"name":"Alice"}
^
|
headers
                ^
                |
             body
```

Алгоритм примерно такой:

```text
1. Читать TCP
        |
        v
2. Найти \r\n\r\n
        |
        v
3. Распарсить headers
        |
        v
4. Найти Content-Length
        |
        v
5. Читать, пока не получено всё body
        |
        v
6. Передать request router'у
```

Именно поэтому настоящий HTTP-сервер намного сложнее нашего учебного примера.

---

# Общая схема проекта

```text
                         INTERNET / CLIENTS

                User A                     User B
               Firefox                    Firefox
                  |                          |
                  | TCP                      | TCP
                  |                          |
                  +------------+-------------+
                               |
                               v
                    +---------------------+
                    |    TCP LISTENER     |
                    |   127.0.0.1:8080    |
                    +---------------------+
                               |
                         listener.Accept()
                               |
                               v
                    +---------------------+
                    |   TCP CONNECTION    |
                    |       conn          |
                    +---------------------+
                               |
                          conn.Read()
                               |
                               v
                    +---------------------+
                    |     RAW BYTES       |
                    +---------------------+
                               |
                               v
                    +---------------------+
                    |    HTTP PARSER      |
                    |                     |
                    | method = GET        |
                    | path = /users       |
                    +---------------------+
                               |
                               v
                    +---------------------+
                    |       ROUTER        |
                    |                     |
                    | "/"      -> home    |
                    | "/users" -> users   |
                    +---------------------+
                               |
                               v
                    +---------------------+
                    |       HANDLER       |
                    |      users()        |
                    +---------------------+
                               |
                               v
                    +---------------------+
                    |    HTTP RESPONSE    |
                    |     200 OK          |
                    +---------------------+
                               |
                          conn.Write()
                               |
                               v
                         TCP connection
                               |
                               v
                            Browser
```

---

# Что мы реализовали сами

В этом проекте вручную сделаны:

```text
TCP listener
TCP accept
TCP read/write
HTTP request parsing
Router
Handlers
HTTP response generation
```

В реальном Go приложении пакет:

```go
net/http
```

берёт большую часть TCP и HTTP логики на себя.

Тогда разработчик обычно работает уже примерно на уровне:

```text
HTTP request
     |
     v
 router
     |
     v
 handler
```

Именно это и является следующим логичным шагом после этого проекта.
