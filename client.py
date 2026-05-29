import threading
import socket
import time
import tkinter as tk

DISCOVERY_PORT = 5001
DISCOVERY_MSG = b"DISCOVER_LAN_CHAT"
RESPONSE_PREFIX = b"DISCOVER_RESPONSE:"
root = tk.Tk()
root.withdraw()

notification_popup = None

# UI COLORS
SURFACE = "#06100b"
TERMINAL_BG = "#000000"
TERMINAL_TEXT = "#9cffc7"
TERMINAL_PROMPT = "#00ff66"

def is_server_online(ip, port, timeout=1):
    try:
        with socket.create_connection((ip, port), timeout):
            return True
    except Exception:
        return False

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

            decoded = msg.decode()

            print("\n" + decoded)

            # Sender extract
            sender = "Unknown"

            if ":" in decoded:
                sender = decoded.split(":")[0]

            # Tkinter popup notification
            root.after(
                0,
                lambda s=sender, m=decoded:
                show_message_notification(s, m)
            )

        except:
            break

def show_message_notification(sender, msg):
    global notification_popup

    try:
        if notification_popup is not None and notification_popup.winfo_exists():
            notification_popup.destroy()
    except:
        pass

    preview = msg if len(msg) <= 70 else f"{msg[:67]}..."

    notification_popup = tk.Toplevel(root)
    notification_popup.title("LAN Chat Notification")
    notification_popup.configure(bg=TERMINAL_BG)
    notification_popup.overrideredirect(True)
    notification_popup.attributes("-topmost", True)

    panel = tk.Frame(
        notification_popup,
        bg=SURFACE,
        highlightthickness=1,
        highlightbackground=TERMINAL_PROMPT,
        bd=0
    )

    panel.pack(fill="both", expand=True)

    tk.Label(
        panel,
        text=f"> incoming packet :: {sender}",
        bg=SURFACE,
        fg=TERMINAL_PROMPT,
        font=("Consolas", 10, "bold"),
        anchor="w",
        padx=12
    ).pack(fill="x", pady=(10, 2))

    tk.Label(
        panel,
        text=preview,
        bg=SURFACE,
        fg=TERMINAL_TEXT,
        font=("Consolas", 10),
        anchor="w",
        justify="left",
        wraplength=300,
        padx=12
    ).pack(fill="x", pady=(0, 10))

    root.update_idletasks()

    width = 340
    height = 82

    screen_width = root.winfo_screenwidth()

    x = screen_width - width - 20
    y = 40

    notification_popup.geometry(
        f"{width}x{height}+{x}+{y}"
    )

    notification_popup.after(
        4500,
        notification_popup.destroy
    )

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
    if not is_server_online(ip, port, timeout=2):
        print(f"Server {ip}:{port} is not reachable.")
        return
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
    threading.Thread(
        target=main,
        daemon=True
    ).start()

    root.mainloop()