import threading
import socket
import time

DISCOVERY_PORT = 5001
DISCOVERY_MSG = b"DISCOVER_LAN_CHAT"
RESPONSE_PREFIX = b"DISCOVER_RESPONSE:"

def discover(timeout=2):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    servers = {}
    try:
        sock.sendto(DISCOVERY_MSG, ('<broadcast>', DISCOVERY_PORT))
        sock.sendto(DISCOVERY_MSG, ('255.255.255.255', DISCOVERY_PORT))
    except Exception:
        pass

    start = time.time()
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if data.startswith(RESPONSE_PREFIX):
                try:
                    port = int(data.decode().split(':')[1])
                except:
                    port = 5000
                servers[addr[0]] = port
        except socket.timeout:
            break
        except:
            if time.time() - start > timeout:
                break

    sock.close()
    return list(servers.items())

def receive_messages(client):
    while True:
        try:
            msg = client.recv(1024)
            if not msg:
                break
            print("\n" + msg.decode())
        except:
            break

def main():
    servers = discover()
    if servers:
        print("Discovered servers:")
        for i, (ip, port) in enumerate(servers):
            print(f"{i+1}) {ip}:{port}")
        choice = input("Choose server number or press Enter for first: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(servers):
            ip, port = servers[int(choice) - 1]
        else:
            ip, port = servers[0]
    else:
        ip = input("No servers found. Enter server IP: ").strip()
        port = 5000

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((ip, port))
    except Exception as e:
        print("Connect failed:", e)
        return

    # Expect server to ask for nick
    try:
        data = client.recv(1024).decode()
    except:
        data = ''

    if data == "ENTER_NICK":
        nick = input("Your Name: ").strip()
        client.send(nick.encode())
    else:
        nick = input("Your Name: ").strip()
        client.send(nick.encode())

    print("Connected to chat. Type messages and press Enter. Ctrl+C to quit.")

    threading.Thread(target=receive_messages, args=(client,), daemon=True).start()

    try:
        while True:
            msg = input()
            if not msg:
                continue
            client.send(msg.encode())
    except KeyboardInterrupt:
        print("Exiting.")
    finally:
        try:
            client.close()
        except:
            pass


if __name__ == '__main__':
    main()