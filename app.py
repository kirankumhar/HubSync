import functools
import json
import os
import re
import socket
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter as tk

import requests
from flask import Flask, jsonify, request

# ==========================================
# CONFIG
# ==========================================
PORT = 5000
LOCK_PIN = "#kiran1991"
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "hubsync_history.json")
BG = "#0f172a"
SURFACE = "#111827"
SURFACE_2 = "#1f2937"
TERMINAL_BG = "#020617"
TERMINAL_TEXT = "#d1fae5"
TERMINAL_PROMPT = "#22c55e"
TEXT = "#e5e7eb"
MUTED = "#94a3b8"
PRIMARY = "#3b82f6"
PRIMARY_ACTIVE = "#60a5fa"
DANGER = "#ef4444"
SUCCESS = "#22c55e"
BORDER = "#334155"
LINK = "#93c5fd"

# ==========================================
# FLASK APP
# ==========================================
app = Flask(__name__)

# ==========================================
# GET USERNAME + LOCAL IP
# ==========================================
USERNAME = socket.gethostname()


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()

    return ip


LOCAL_IP = get_local_ip()

# ==========================================
# ONLINE USERS
# ==========================================
online_users = {}
SYSTEM_CHAT = "__system__"
current_chat_key = SYSTEM_CHAT


def load_chat_histories():
    if not os.path.exists(HISTORY_FILE):
        return {SYSTEM_CHAT: []}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {SYSTEM_CHAT: []}

    histories = {}
    for chat_key, messages in data.get("histories", {}).items():
        if not isinstance(chat_key, str) or not isinstance(messages, list):
            continue

        clean_messages = []
        for item in messages:
            if (
                isinstance(item, list)
                and len(item) == 2
                and isinstance(item[0], str)
                and isinstance(item[1], str)
            ):
                clean_messages.append((item[0], item[1]))

        histories[chat_key] = clean_messages

    histories.setdefault(SYSTEM_CHAT, [])
    return histories


def save_chat_histories():
    data = {
        "histories": chat_histories
    }

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
    except OSError:
        pass


chat_histories = load_chat_histories()

# ==========================================
# FLASK ROUTES
# ==========================================
@app.route("/")
def home():
    return "HubSync Running"


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({
        "username": USERNAME,
        "ip": LOCAL_IP
    })


@app.route("/message", methods=["POST"])
def message():
    data = request.json

    sender = data.get("sender")
    msg = data.get("message")
    sender_ip = request.remote_addr

    if sender and msg:
        root.after(
            0,
            lambda: receive_message(sender, msg, sender_ip)
        )

    return "OK"


# ==========================================
# CHAT HISTORY + BOX UPDATE
# ==========================================
def get_message_tag(text):
    if text.startswith("Me:"):
        return "me"
    if text.startswith(("Send Failed:", "Server Error:")):
        return "error"
    if ": " in text:
        return "peer"
    return "system"


def add_chat_message(text, chat_key=SYSTEM_CHAT):
    timestamp = datetime.now().strftime("%H:%M")
    line = f"[{timestamp}] {text}\n"
    tag = get_message_tag(text)
    chat_histories.setdefault(chat_key, []).append((line, tag))
    save_chat_histories()

    if chat_key == current_chat_key:
        render_chat_history()


def render_chat_history():
    chat_box.delete("1.0", tk.END)

    for line, tag in chat_histories.get(current_chat_key, []):
        chat_box.insert(tk.END, line, tag)

    chat_box.see(tk.END)
    make_links_clickable()


def set_current_chat(chat_key, title):
    global current_chat_key

    current_chat_key = chat_key
    conversation_title_var.set(title)
    chat_histories.setdefault(chat_key, [])
    render_chat_history()


def receive_message(sender, msg, sender_ip):
    if sender_ip not in online_users:
        online_users[sender_ip] = sender
        user_listbox.insert(tk.END, f"{sender} - {sender_ip}")

    add_chat_message(f"{sender}: {msg}", sender_ip)


def make_links_clickable():
    for tag in chat_box.tag_names():
        if tag.startswith("url_"):
            chat_box.tag_delete(tag)

    content = chat_box.get("1.0", tk.END)
    for m in re.finditer(r"https?://[^\s]+", content):
        start_idx = f"1.0+{m.start()}c"
        end_idx = f"1.0+{m.end()}c"
        tag_name = f"url_{m.start()}"
        chat_box.tag_add(tag_name, start_idx, end_idx)
        chat_box.tag_config(tag_name, foreground=LINK, underline=1)
        url = m.group(0)

        def open_url(event, url=url):
            webbrowser.open(url)

        chat_box.tag_bind(tag_name, "<Button-1>", open_url)


# ==========================================
# START FLASK SERVER
# ==========================================
def start_server():
    try:
        app.run(
            host="0.0.0.0",
            port=PORT,
            threaded=True,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        root.after(0, lambda: add_chat_message(f"Server Error: {e}"))


# ==========================================
# SEND MESSAGE
# ==========================================
def send_message():
    selected = user_listbox.curselection()

    if not selected:
        messagebox.showwarning(
            "Warning",
            "Select one or more devices first"
        )
        return

    message_text = msg_entry.get("1.0", tk.END).strip()

    if not message_text:
        return

    selected_users = [user_listbox.get(index) for index in selected]
    sent_count = 0
    sent_names = []

    for selected_user in selected_users:
        target_name, target_ip = selected_user.rsplit(" - ", 1)

        try:
            requests.post(
                f"http://{target_ip}:{PORT}/message",
                json={
                    "sender": USERNAME,
                    "message": message_text
                },
                timeout=2
            )
            sent_count += 1
            sent_names.append(target_name)
            add_chat_message(f"Me: {message_text}", target_ip)

        except Exception as e:
            add_chat_message(f"Send Failed: {e}", target_ip)

    if sent_count:
        status_var.set(f"Sent to {', '.join(sent_names)}")
        msg_entry.delete("1.0", tk.END)
        msg_entry.focus_set()


# ==========================================
# CHECK SINGLE HOST
# ==========================================
def check_host(ip):
    try:
        response = requests.get(
            f"http://{ip}:{PORT}/ping",
            timeout=1
        )

        if response.status_code == 200:
            data = response.json()
            username = data.get("username")

            if ip not in online_users:
                online_users[ip] = username

                root.after(
                    0,
                    lambda: user_listbox.insert(
                        tk.END,
                        f"{username} - {ip}"
                    )
                )

    except Exception:
        pass


# ==========================================
# SCAN NETWORK
# ==========================================
def scan_network():
    root.after(0, lambda: scan_btn.config(state="disabled"))
    root.after(0, lambda: status_var.set("Scanning for devices..."))
    root.after(0, lambda: user_listbox.delete(0, tk.END))

    online_users.clear()
    root.after(0, lambda: add_chat_message("Scanning network..."))

    base_ip = ".".join(LOCAL_IP.split(".")[:-1])

    with ThreadPoolExecutor(max_workers=100) as executor:
        for i in range(1, 255):
            ip = f"{base_ip}.{i}"

            if ip == LOCAL_IP:
                continue

            executor.submit(check_host, ip)

    root.after(0, lambda: add_chat_message("Scan completed"))
    root.after(0, lambda: scan_btn.config(state="normal"))
    root.after(0, lambda: status_var.set(f"{len(online_users)} device(s) online"))


# ==========================================
# START SCAN THREAD
# ==========================================
def start_scan():
    threading.Thread(
        target=scan_network,
        daemon=True
    ).start()


# ==========================================
# GUI
# ==========================================
root = tk.Tk()
root.title(f"HubSync - {USERNAME}")
root.geometry("860x640")
root.minsize(720, 520)
root.configure(bg=BG)

style = ttk.Style(root)
style.theme_use("clam")
style.configure(".", font=("Segoe UI", 10), background=BG, foreground=TEXT)
style.configure("App.TFrame", background=BG)
style.configure("Surface.TFrame", background=SURFACE, borderwidth=1, relief="solid")
style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 18, "bold"))
style.configure("Subtle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
style.configure("Section.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI", 10, "bold"))
style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
style.configure("Primary.TButton", background=PRIMARY, foreground="white", borderwidth=0, padding=(14, 8))
style.map("Primary.TButton", background=[("active", PRIMARY_ACTIVE), ("disabled", "#475569")])
style.configure("Success.TButton", background=SUCCESS, foreground="white", borderwidth=0, padding=(16, 8))
style.map("Success.TButton", background=[("active", "#4ade80")])
style.configure("Danger.TButton", background=DANGER, foreground="white", borderwidth=0, padding=(12, 8))
style.map("Danger.TButton", background=[("active", "#f87171")])
style.configure("Ghost.TButton", background=SURFACE_2, foreground=TEXT, borderwidth=0, padding=(12, 8))
style.map("Ghost.TButton", background=[("active", "#374151")])

main = ttk.Frame(root, style="App.TFrame", padding=18)
main.pack(fill="both", expand=True)

lock_screen = ttk.Frame(root, style="App.TFrame", padding=28)


def show_main_screen():
    lock_screen.pack_forget()
    main.pack(fill="both", expand=True)
    msg_entry.focus_set()


def show_lock_screen():
    main.pack_forget()
    lock_error_var.set("")
    lock_pin_var.set("")
    lock_screen.pack(fill="both", expand=True)
    lock_entry.focus_set()


def unlock_app(event=None):
    if lock_pin_var.get() == LOCK_PIN:
        show_main_screen()
        return "break"

    lock_error_var.set("Wrong PIN")
    lock_pin_var.set("")
    lock_entry.focus_set()
    return "break"


lock_screen.columnconfigure(0, weight=1)
lock_screen.rowconfigure(0, weight=1)

lock_panel = ttk.Frame(lock_screen, style="Surface.TFrame", padding=28)
lock_panel.grid(row=0, column=0)

ttk.Label(
    lock_panel,
    text="HubSync Locked",
    style="Section.TLabel"
).pack(anchor="center")
ttk.Label(
    lock_panel,
    text="Enter PIN to continue",
    style="Muted.TLabel"
).pack(anchor="center", pady=(6, 18))

lock_pin_var = tk.StringVar()
lock_error_var = tk.StringVar()

lock_entry = tk.Entry(
    lock_panel,
    textvariable=lock_pin_var,
    show="*",
    font=("Consolas", 14),
    bg=TERMINAL_BG,
    fg=TERMINAL_TEXT,
    insertbackground=TERMINAL_PROMPT,
    relief="flat",
    width=18,
    justify="center",
    highlightthickness=1,
    highlightbackground=BORDER,
    highlightcolor=TERMINAL_PROMPT
)
lock_entry.pack(fill="x")
lock_entry.bind("<Return>", unlock_app)

ttk.Label(
    lock_panel,
    textvariable=lock_error_var,
    style="Muted.TLabel"
).pack(anchor="center", pady=(8, 10))

unlock_btn = ttk.Button(
    lock_panel,
    text="Unlock",
    command=unlock_app,
    style="Success.TButton"
)
unlock_btn.pack(fill="x")

# ==========================================
# TOP FRAME
# ==========================================
top_frame = ttk.Frame(main, style="App.TFrame")
top_frame.pack(fill="x")

title_block = ttk.Frame(top_frame, style="App.TFrame")
title_block.pack(side="left", fill="x", expand=True)

ttk.Label(title_block, text="HubSync", style="Header.TLabel").pack(anchor="w")
ttk.Label(
    title_block,
    text=f"{USERNAME} on {LOCAL_IP}",
    style="Subtle.TLabel"
).pack(anchor="w", pady=(2, 0))

status_var = tk.StringVar(value="Ready")
status_label = ttk.Label(top_frame, textvariable=status_var, style="Subtle.TLabel")
status_label.pack(side="right", padx=(12, 0))

lock_btn = ttk.Button(
    top_frame,
    text="Lock",
    command=show_lock_screen,
    style="Ghost.TButton"
)
lock_btn.pack(side="right", padx=(0, 10))

scan_btn = ttk.Button(
    top_frame,
    text="Scan Devices",
    command=start_scan,
    style="Primary.TButton"
)
scan_btn.pack(side="right")

# ==========================================
# DEVICE LIST + CHAT
# ==========================================
content = ttk.Frame(main, style="App.TFrame")
content.pack(fill="both", expand=True, pady=(18, 0))
content.columnconfigure(0, weight=0, minsize=260)
content.columnconfigure(1, weight=1)
content.rowconfigure(0, weight=1)

device_panel = ttk.Frame(content, style="Surface.TFrame", padding=12)
device_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

ttk.Label(device_panel, text="Online Devices", style="Section.TLabel").pack(anchor="w")
ttk.Label(device_panel, text="Select one or more devices before sending.", style="Muted.TLabel").pack(anchor="w", pady=(2, 10))

user_listbox = tk.Listbox(
    device_panel,
    height=12,
    font=("Segoe UI", 10),
    bg=SURFACE,
    fg=TEXT,
    selectbackground=PRIMARY,
    selectforeground="white",
    highlightthickness=1,
    highlightbackground=BORDER,
    highlightcolor=PRIMARY,
    borderwidth=0,
    activestyle="none",
    selectmode=tk.EXTENDED
)
user_listbox.pack(fill="both", expand=True)


def on_device_select(event=None):
    selected = user_listbox.curselection()

    if not selected:
        set_current_chat(SYSTEM_CHAT, "System")
        return

    active_index = user_listbox.index("active")
    if active_index not in selected:
        active_index = selected[-1]

    selected_user = user_listbox.get(active_index)
    target_name, target_ip = selected_user.rsplit(" - ", 1)
    set_current_chat(target_ip, f"Conversation with {target_name}")


user_listbox.bind("<<ListboxSelect>>", on_device_select)

chat_panel = ttk.Frame(content, style="Surface.TFrame", padding=12)
chat_panel.grid(row=0, column=1, sticky="nsew")
chat_panel.rowconfigure(1, weight=1)
chat_panel.columnconfigure(0, weight=1)

conversation_title_var = tk.StringVar(value="System")
ttk.Label(
    chat_panel,
    textvariable=conversation_title_var,
    style="Section.TLabel"
).grid(row=0, column=0, sticky="w", pady=(0, 10))

chat_box = scrolledtext.ScrolledText(
    chat_panel,
    font=("Consolas", 10),
    bg=SURFACE_2,
    fg=TEXT,
    wrap="word",
    relief="flat",
    borderwidth=0,
    padx=12,
    pady=10,
    insertbackground=TEXT,
    selectbackground=PRIMARY,
    selectforeground="white"
)
chat_box.grid(row=1, column=0, sticky="nsew")
chat_box.tag_config("me", foreground=PRIMARY)
chat_box.tag_config("peer", foreground=TEXT)
chat_box.tag_config("system", foreground=MUTED)
chat_box.tag_config("error", foreground=DANGER)

# ==========================================
# MESSAGE FRAME
# ==========================================
bottom_frame = ttk.Frame(main, style="App.TFrame")
bottom_frame.pack(fill="x", pady=(14, 0))
bottom_frame.columnconfigure(0, weight=1)

terminal_input = tk.Frame(
    bottom_frame,
    bg=TERMINAL_BG,
    highlightthickness=1,
    highlightbackground=BORDER,
    highlightcolor=TERMINAL_PROMPT,
    bd=0
)
terminal_input.grid(row=0, column=0, sticky="ew")
terminal_input.columnconfigure(1, weight=1)

prompt_label = tk.Label(
    terminal_input,
    text=">",
    font=("Consolas", 15, "bold"),
    bg=TERMINAL_BG,
    fg=TERMINAL_PROMPT,
    padx=10,
    pady=8
)
prompt_label.grid(row=0, column=0, sticky="nw")

msg_entry = tk.Text(
    terminal_input,
    height=3,
    font=("Consolas", 11),
    wrap="word",
    bg=TERMINAL_BG,
    fg=TERMINAL_TEXT,
    relief="flat",
    borderwidth=0,
    highlightthickness=0,
    padx=0,
    pady=8,
    insertbackground=TERMINAL_PROMPT,
    selectbackground=PRIMARY,
    selectforeground="white"
)
msg_entry.grid(row=0, column=1, sticky="ew")

actions = ttk.Frame(bottom_frame, style="App.TFrame")
actions.grid(row=0, column=1, sticky="ns", padx=(10, 0))

send_btn = ttk.Button(
    actions,
    text="Send",
    command=send_message,
    style="Success.TButton"
)
send_btn.pack(fill="x")


def open_emoji_picker():
    picker = tk.Toplevel(root)
    picker.title("Quick Phrases")
    picker.configure(bg=BG)
    picker.transient(root)
    picker.resizable(False, False)
    phrases = [
        ":)", ":D", ":P", ";)",
        "<3", "OK", "Thanks", "Nice",
        "+1", "Done", "Great", "Cool",
        "Idea", "Haha", "Deal", "Hmm"
    ]

    def insert_phrase(phrase):
        msg_entry.insert(tk.INSERT, phrase)
        picker.destroy()

    for i, phrase in enumerate(phrases):
        button = ttk.Button(
            picker,
            text=phrase,
            width=7,
            command=lambda phrase=phrase: insert_phrase(phrase),
            style="Ghost.TButton"
        )
        button.grid(row=i // 4, column=i % 4, padx=4, pady=4)


emoji_btn = ttk.Button(
    actions,
    text="Phrases",
    command=open_emoji_picker,
    style="Ghost.TButton"
)
emoji_btn.pack(fill="x", pady=(8, 0))


def clear_chat():
    chat_histories[current_chat_key] = []
    save_chat_histories()
    chat_box.delete("1.0", tk.END)


clear_btn = ttk.Button(
    actions,
    text="Clear Chat",
    command=clear_chat,
    style="Ghost.TButton"
)
clear_btn.pack(fill="x", pady=(8, 0))

# ==========================================
# FOLDER SHARE CONTROLS
# ==========================================
shared_servers = {}


def start_folder_server(folder):
    port = 8000
    while True:
        try:
            handler = functools.partial(SimpleHTTPRequestHandler, directory=folder)
            httpd = ThreadingHTTPServer((LOCAL_IP, port), handler)
            break
        except OSError:
            port += 1

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    shared_servers[folder] = (httpd, port)
    return port


def stop_all_shares():
    for folder, (httpd, port) in list(shared_servers.items()):
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass
        del shared_servers[folder]
    add_chat_message("Stopped sharing all folders")


def share_folder():
    folder = filedialog.askdirectory()
    if not folder:
        return
    if folder in shared_servers:
        add_chat_message(f"Already sharing: {folder}")
        return
    port = start_folder_server(folder)
    url = f"http://{LOCAL_IP}:{port}/"
    add_chat_message(f"Sharing folder {os.path.basename(folder)} at {url}")

    selected = user_listbox.curselection()
    for index in selected:
        selected_user = user_listbox.get(index)
        target_ip = selected_user.rsplit(" - ", 1)[1]
        try:
            requests.post(
                f"http://{target_ip}:{PORT}/message",
                json={
                    "sender": USERNAME,
                    "message": f"FOLDER_SHARED: {USERNAME} shared {os.path.basename(folder)} {url}"
                },
                timeout=2
            )
        except Exception:
            add_chat_message("Failed to notify target about shared folder")


share_btn = ttk.Button(
    actions,
    text="Share Folder",
    command=share_folder,
    style="Primary.TButton"
)
share_btn.pack(fill="x", pady=(8, 0))

stop_share_btn = ttk.Button(
    actions,
    text="Stop Sharing",
    command=stop_all_shares,
    style="Danger.TButton"
)
stop_share_btn.pack(fill="x", pady=(8, 0))


def on_ctrl_enter(event=None):
    send_message()
    return "break"


msg_entry.bind("<Control-Return>", on_ctrl_enter)


def on_close():
    save_chat_histories()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)

# ==========================================
# START FLASK SERVER THREAD
# ==========================================
threading.Thread(
    target=start_server,
    daemon=True
).start()

# ==========================================
# START GUI
# ==========================================
add_chat_message("Server started")
add_chat_message(f"My IP: {LOCAL_IP}")
root.after(800, start_scan)
root.after(100, show_lock_screen)

root.mainloop()
