# Concurrent TCP/HTTP Server: Python Threads and Go Goroutines

## Общая схема

```text
Client A ----\
              \
               -> TCP server -> HTTP parser -> Router -> Handler
              /
Client B ----/
```

Задача сервера: принимать несколько TCP-соединений так, чтобы один медленный клиент не блокировал остальных.

---

# 1. Последовательная обработка

Базовый сервер:

```python
while True:
    conn, addr = server.accept()
    handle_client(conn, addr)
```

Схема:

```text
Client A
   |
   v
accept()
   |
   v
handle A
   |
   v
finish A
   |
   v
accept()
   |
   v
handle B
```

Пока `handle A` не завершится, сервер не начнёт обработку следующего клиента.

---

# 2. Python: отдельный thread на клиента

```python
while True:
    conn, addr = server.accept()

    thread = threading.Thread(
        target=handle_client,
        args=(conn, addr),
    )

    thread.start()
```

Схема:

```text
                    main thread
                        |
                     accept()
                        |
             +----------+----------+
             |                     |
             v                     v
         thread A              thread B
             |                     |
         Client A              Client B
             |                     |
          recv()                  recv()
             |                     |
         handler()              handler()
             |                     |
          send()                  send()
```

Главный поток в основном снова возвращается к `accept()`.

---

# 3. Пример с двумя клиентами

Пусть:

```python
def home():
    time.sleep(5)
    return "home page"

def users():
    return "users page"
```

Клиент A открывает `/`, затем клиент B открывает `/users`.

```text
time ------------------------------------------------->

thread A:
GET /
sleep 5 sec
---------------------------------> response

thread B:
        GET /users
        response
        close
```

Клиент B завершится раньше, хотя подключился позже.

Пример лога:

```text
connected: ('127.0.0.1', 50004)
('127.0.0.1', 50004) GET /

connected: ('127.0.0.1', 50016)
('127.0.0.1', 50016) GET /users

closed: ('127.0.0.1', 50016)
closed: ('127.0.0.1', 50004)
```

---

# 4. Один CPU core

Если у машины одно ядро, потоки не исполняют Python-код физически одновременно.

ОС переключается между ними:

```text
CPU core

thread A ---> thread B ---> thread A ---> thread B
```

Если один поток ждёт:

```python
conn.recv(...)
```

или:

```python
time.sleep(...)
```

другой поток может продолжить работу.

---

# 5. Python thread и OS thread

При использовании:

```python
threading.Thread(...)
```

создаётся системный поток.

```text
Python application

main thread ---------> OS thread
worker thread A -----> OS thread
worker thread B -----> OS thread
worker thread C -----> OS thread
```

---

# 6. Go: goroutine на клиента

В Go:

```go
for {
    conn, err := listener.Accept()
    if err != nil {
        continue
    }

    go handleClient(conn)
}
```

Ключевая строка:

```go
go handleClient(conn)
```

Без `go`:

```go
handleClient(conn)
```

текущая goroutine ждёт завершения функции.

С `go`:

```go
go handleClient(conn)
```

создаётся новая goroutine, а текущая продолжает выполнение.

---

# 7. Схема Go-сервера

```text
                    main goroutine
                         |
                      Accept()
                         |
              +----------+----------+
              |                     |
              v                     v
         goroutine A           goroutine B
              |                     |
           Client A              Client B
              |                     |
           Read()                  Read()
              |                     |
         handler()              handler()
              |                     |
          Write()                 Write()
```

---

# 8. Goroutine != OS thread

Goroutine — не системный поток.

Это лёгкая единица выполнения, которой управляет Go runtime.

```text
goroutine A ----\
goroutine B -----\
goroutine C ------> Go runtime scheduler ---> OS thread 1
goroutine D -----/                         ---> OS thread 2
goroutine E ----/
```

Go runtime решает:

```text
какую goroutine
когда
на каком OS thread
выполнять
```

---

# 9. Если goroutine ждёт сеть

Например:

```go
n, err := conn.Read(buffer)
```

Если данных пока нет, эта goroutine ждёт.

Go runtime может выполнять другие goroutine.

```text
goroutine A
   |
   v
conn.Read()
   |
   | waiting for network
   |
   +----------------------+

goroutine B
             |
             v
          handler()
             |
             v
          response
```

Код остаётся синхронным:

```go
conn.Read(...)
time.Sleep(...)
conn.Write(...)
```

Конкурентностью управляет runtime.

---

# 10. Python threads vs Go goroutines

Python:

```text
Client A ---> thread A ---> OS thread
Client B ---> thread B ---> OS thread
Client C ---> thread C ---> OS thread
```

Go:

```text
Client A ---> goroutine A --\
Client B ---> goroutine B ----> Go runtime ---> OS threads
Client C ---> goroutine C --/
```

Коротко:

```text
Python threading:
один worker = OS thread

Go:
один worker = goroutine
goroutine multiplexed на OS threads
```

---

# 11. Где TCP и где HTTP

Модель конкурентности не меняет TCP или HTTP.

```text
TCP connection
      |
      v
Read / recv
      |
      v
raw bytes
      |
      v
HTTP parser
      |
      v
method + path + headers + body
      |
      v
router
      |
      v
handler
      |
      v
HTTP response
      |
      v
Write / send
      |
      v
TCP connection
```

Threads и goroutines меняют только способ одновременной обработки нескольких соединений.

---

# 12. Полная схема

```text
                    CLIENT A
                       |
                       | TCP
                       v
                 +-------------+
                 | connection A|
                 +-------------+
                       |
                       |
                       |                CLIENT B
                       |                   |
                       |                   | TCP
                       |                   v
                       |             +-------------+
                       |             | connection B|
                       |             +-------------+
                       |                   |
                       +---------+---------+
                                 |
                                 v
                        +----------------+
                        | TCP LISTENER   |
                        +----------------+
                                 |
                              Accept()
                                 |
              +------------------+------------------+
              |                                     |
              v                                     v
        worker A                               worker B
   thread / goroutine                     thread / goroutine
              |                                     |
              v                                     v
          HTTP parse                            HTTP parse
              |                                     |
              v                                     v
            router                                router
              |                                     |
              v                                     v
           handler A                             handler B
              |                                     |
              v                                     v
         HTTP response                         HTTP response
              |                                     |
              v                                     v
           TCP write                             TCP write
```

---

# 13. Главное различие

Python:

```text
threading.Thread(...)
        |
        v
OS thread
```

Go:

```text
go function()
      |
      v
goroutine
      |
      v
Go runtime scheduler
      |
      v
OS threads
```

TCP и HTTP остаются теми же.
