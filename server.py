import socket
import threading

HOST = '0.0.0.0'
PORT = 5000
DISCOVERY_PORT = 5001
DISCOVERY_MSG = b"DISCOVER_LAN_CHAT"
RESPONSE_PREFIX = b"DISCOVER_RESPONSE:"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()

# clients: list of tuples (socket, nickname)
clients = []
clients_lock = threading.Lock()

print("Server started...")
print("Waiting for connections...")

def broadcast(message, exclude=None):
    with clients_lock:
        for client, _ in clients:
            if client is exclude:
                continue
            try:
                client.send(message)
            except:
                pass

def handle_client(client, addr):
    nick = None
    try:
        # Ask for nickname
        client.send("ENTER_NICK".encode())
        nick = client.recv(1024).decode().strip()
        if not nick:
            nick = f"{addr[0]}:{addr[1]}"

        with clients_lock:
            clients.append((client, nick))

        print(f"{nick} joined from {addr}")
        broadcast(f"*** {nick} joined the chat ***".encode())

        while True:
            message = client.recv(1024)
            if not message:
                break
            text = message.decode().strip()
            full = f"{nick}: {text}"
            print(full)
            broadcast(full.encode(), exclude=client)

    except Exception as e:
        print(f"Client error: {e}")

    finally:
        with clients_lock:
            clients[:] = [(c, n) for (c, n) in clients if c is not client]

        if nick:
            broadcast(f"*** {nick} left the chat ***".encode())

        try:
            client.close()
        except:
            pass

def discovery_service():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", DISCOVERY_PORT))
    except Exception as e:
        print("Discovery bind failed:", e)
        return

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if data == DISCOVERY_MSG:
                resp = f"{RESPONSE_PREFIX.decode()}{PORT}".encode()
                sock.sendto(resp, addr)
        except:
            pass

threading.Thread(target=discovery_service, daemon=True).start()

while True:
    client, addr = server.accept()

    print(f"Connected: {addr}")

    threading.Thread(
        target=handle_client,
        args=(client, addr),
        daemon=True
    ).start()
