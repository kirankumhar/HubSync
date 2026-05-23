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
AUTO_LOCK_MS = 5 * 60 * 1000
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "hubsync_history.json")
BG = "#030712"
SURFACE = "#050a08"
SURFACE_2 = "#07130d"
TERMINAL_BG = "#000000"
TERMINAL_TEXT = "#9cffb3"
TERMINAL_PROMPT = "#00ff66"
TEXT = "#d7ffe2"
MUTED = "#5ee787"
PRIMARY = "#00d9ff"
PRIMARY_ACTIVE = "#67e8f9"
DANGER = "#ff3b5c"
SUCCESS = "#00ff66"
BORDER = "#14532d"
LINK = "#22d3ee"

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
auto_lock_job = None
is_locked = False
notification_popup = None


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
    show_message_notification(sender, msg)


def show_message_notification(sender, msg):
    global notification_popup

    if notification_popup is not None and notification_popup.winfo_exists():
        notification_popup.destroy()

    preview = msg if len(msg) <= 70 else f"{msg[:67]}..."

    notification_popup = tk.Toplevel(root)
    notification_popup.title("HubSync Notification")
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
    x = root.winfo_x() + root.winfo_width() - width - 24
    y = root.winfo_y() + 48
    notification_popup.geometry(f"{width}x{height}+{x}+{y}")
    notification_popup.after(4500, notification_popup.destroy)


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
                root.after(0, refresh_device_count)

    except Exception:
        pass


# ==========================================
# SCAN NETWORK
# ==========================================
def scan_network():
    root.after(0, lambda: scan_btn.config(state="disabled"))
    root.after(0, lambda: status_var.set("Scanning for devices..."))
    root.after(0, lambda: user_listbox.delete(0, tk.END))
    root.after(0, refresh_device_count)

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
    root.after(0, refresh_device_count)


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
root.title(f"HubSync - Terminal Edition")
root.geometry("1280x760")
root.minsize(1040, 640)
root.configure(bg=BG)

style = ttk.Style(root)
style.theme_use("clam")
style.configure(".", font=("Consolas", 10), background=BG, foreground=TEXT)
style.configure("App.TFrame", background=BG)
style.configure("Surface.TFrame", background=SURFACE, borderwidth=1, relief="solid")
style.configure("Header.TLabel", background=BG, foreground=TERMINAL_PROMPT, font=("Consolas", 20, "bold"))
style.configure("Subtle.TLabel", background=BG, foreground=MUTED, font=("Consolas", 10))
style.configure("Section.TLabel", background=SURFACE, foreground=TERMINAL_PROMPT, font=("Consolas", 10, "bold"))
style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=("Consolas", 9))
style.configure("Primary.TButton", background="#062b2f", foreground=PRIMARY, borderwidth=0, padding=(14, 8))
style.map("Primary.TButton", background=[("active", "#083f46"), ("disabled", "#0f241d")])
style.configure("Success.TButton", background="#063018", foreground=SUCCESS, borderwidth=0, padding=(16, 8))
style.map("Success.TButton", background=[("active", "#0b4a26")])
style.configure("Danger.TButton", background="#3a0713", foreground=DANGER, borderwidth=0, padding=(12, 8))
style.map("Danger.TButton", background=[("active", "#5f0b1d")])
style.configure("Ghost.TButton", background=SURFACE_2, foreground=TERMINAL_TEXT, borderwidth=0, padding=(12, 8))
style.map("Ghost.TButton", background=[("active", "#0c2618")])

main = ttk.Frame(root, style="App.TFrame", padding=14)
main.pack(fill="both", expand=True)

lock_screen = ttk.Frame(root, style="App.TFrame", padding=28)


def show_main_screen():
    global is_locked

    is_locked = False
    lock_screen.pack_forget()
    main.pack(fill="both", expand=True)
    msg_entry.focus_set()
    reset_auto_lock_timer()


def show_lock_screen():
    global auto_lock_job, is_locked

    if is_locked:
        return

    is_locked = True
    if auto_lock_job is not None:
        root.after_cancel(auto_lock_job)
        auto_lock_job = None
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


def reset_auto_lock_timer(event=None):
    global auto_lock_job

    if is_locked:
        return

    if auto_lock_job is not None:
        root.after_cancel(auto_lock_job)

    auto_lock_job = root.after(AUTO_LOCK_MS, show_lock_screen)


def lock_when_minimized(event=None):
    if root.state() == "iconic":
        show_lock_screen()


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
    text="AUTH REQUIRED // enter PIN",
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
# TERMINAL DASHBOARD
# ==========================================
def make_panel(parent, title=None, padding=10):
    frame = tk.Frame(
        parent,
        bg=TERMINAL_BG,
        highlightthickness=1,
        highlightbackground=TERMINAL_PROMPT,
        bd=0
    )
    if title:
        tk.Label(
            frame,
            text=title,
            bg=TERMINAL_BG,
            fg=TERMINAL_PROMPT,
            font=("Consolas", 11, "bold"),
            anchor="w",
            padx=padding
        ).pack(fill="x", pady=(padding, 6))
    return frame


top_frame = tk.Frame(main, bg=BG)
top_frame.pack(fill="x")

title_block = tk.Frame(top_frame, bg=BG)
title_block.pack(side="left", fill="x", expand=True)

tk.Label(
    title_block,
    text="} HUBSYNC TERMINAL",
    bg=BG,
    fg=TERMINAL_PROMPT,
    font=("Consolas", 20, "bold"),
    anchor="w"
).pack(anchor="w")
tk.Label(
    title_block,
    text=f"}} Connected to {LOCAL_IP}",
    bg=BG,
    fg=TERMINAL_PROMPT,
    font=("Consolas", 11),
    anchor="w"
).pack(anchor="w")

status_var = tk.StringVar(value="Ready")
status_pill = make_panel(top_frame)
status_pill.pack(side="left", padx=18)
tk.Label(
    status_pill,
    textvariable=status_var,
    bg=TERMINAL_BG,
    fg=TERMINAL_TEXT,
    font=("Consolas", 11),
    padx=24,
    pady=12
).pack()

top_actions = tk.Frame(top_frame, bg=BG)
top_actions.pack(side="right")

scan_btn = ttk.Button(
    top_actions,
    text="[S] Scan Devices",
    command=start_scan,
    style="Primary.TButton"
)
scan_btn.pack(side="left", padx=(0, 10))

lock_btn = ttk.Button(
    top_actions,
    text="[L] Lock",
    command=show_lock_screen,
    style="Ghost.TButton"
)
lock_btn.pack(side="left", padx=(0, 10))

exit_btn = ttk.Button(
    top_actions,
    text="[X] Exit",
    command=root.destroy,
    style="Danger.TButton"
)
exit_btn.pack(side="left")

content = tk.Frame(main, bg=BG)
content.pack(fill="both", expand=True, pady=(18, 0))
content.columnconfigure(0, minsize=270)
content.columnconfigure(1, weight=1)
content.columnconfigure(2, minsize=250)
content.rowconfigure(0, weight=1)

left_column = tk.Frame(content, bg=BG)
left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
left_column.rowconfigure(0, weight=1)

device_panel = make_panel(left_column, "ONLINE DEVICES", padding=10)
device_panel.grid(row=0, column=0, sticky="nsew")
tk.Label(
    device_panel,
    text="ID  DEVICE NAME        IP ADDRESS\n--------------------------------",
    bg=TERMINAL_BG,
    fg="#e6ff99",
    font=("Consolas", 10),
    anchor="w",
    justify="left",
    padx=10
).pack(fill="x", pady=(0, 4))

user_listbox = tk.Listbox(
    device_panel,
    height=12,
    font=("Consolas", 10),
    bg=TERMINAL_BG,
    fg=TERMINAL_TEXT,
    selectbackground=TERMINAL_PROMPT,
    selectforeground=TERMINAL_BG,
    highlightthickness=0,
    borderwidth=0,
    activestyle="none",
    selectmode=tk.EXTENDED,
    exportselection=False
)
user_listbox.pack(fill="both", expand=True, padx=10)

device_total_var = tk.StringVar(value="Total: 0 device(s)")
tk.Label(
    device_panel,
    textvariable=device_total_var,
    bg=TERMINAL_BG,
    fg=TERMINAL_PROMPT,
    font=("Consolas", 10),
    anchor="w",
    padx=10,
    pady=10
).pack(fill="x")


def refresh_device_count():
    device_total_var.set(f"Total: {user_listbox.size()} device(s)")

menu_panel = make_panel(left_column, "MENU", padding=10)
menu_panel.grid(row=1, column=0, sticky="ew", pady=(12, 0))
for menu_text in ("[M] Messages", "[D] Devices", "[P] Phrases", "[S] Settings", "[A] About"):
    tk.Label(
        menu_panel,
        text=menu_text,
        bg=TERMINAL_BG,
        fg=TERMINAL_TEXT,
        font=("Consolas", 10),
        anchor="w",
        padx=12,
        pady=3
    ).pack(fill="x")


def on_device_select(event=None):
    selected = user_listbox.curselection()

    if not selected:
        set_current_chat(SYSTEM_CHAT, "CHAT ROOM - SYSTEM LOG")
        return

    active_index = user_listbox.index("active")
    if active_index not in selected:
        active_index = selected[-1]

    selected_user = user_listbox.get(active_index)
    target_name, target_ip = selected_user.rsplit(" - ", 1)
    set_current_chat(target_ip, f"CHAT ROOM - {target_name} ({target_ip})")


user_listbox.bind("<<ListboxSelect>>", on_device_select)

center_column = tk.Frame(content, bg=BG)
center_column.grid(row=0, column=1, sticky="nsew")
center_column.rowconfigure(0, weight=1)
center_column.columnconfigure(0, weight=1)

chat_panel = make_panel(center_column)
chat_panel.grid(row=0, column=0, sticky="nsew")
chat_panel.rowconfigure(1, weight=1)
chat_panel.columnconfigure(0, weight=1)

conversation_title_var = tk.StringVar(value="CHAT ROOM - SYSTEM LOG")
tk.Label(
    chat_panel,
    textvariable=conversation_title_var,
    bg=TERMINAL_BG,
    fg=TERMINAL_PROMPT,
    font=("Consolas", 11, "bold"),
    anchor="w",
    padx=12
).grid(row=0, column=0, sticky="ew", pady=(10, 8))

chat_box = scrolledtext.ScrolledText(
    chat_panel,
    font=("Consolas", 11),
    bg=TERMINAL_BG,
    fg=TERMINAL_TEXT,
    wrap="word",
    relief="flat",
    borderwidth=0,
    padx=12,
    pady=10,
    insertbackground=TERMINAL_PROMPT,
    selectbackground="#064e3b",
    selectforeground=TERMINAL_TEXT
)
chat_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
chat_box.tag_config("me", foreground="#ff4dff")
chat_box.tag_config("peer", foreground="#38bdf8")
chat_box.tag_config("system", foreground=TERMINAL_PROMPT)
chat_box.tag_config("error", foreground=DANGER)

bottom_frame = make_panel(center_column)
bottom_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
bottom_frame.columnconfigure(0, weight=1)

msg_entry = tk.Text(
    bottom_frame,
    height=3,
    font=("Consolas", 11),
    wrap="word",
    bg=TERMINAL_BG,
    fg=TERMINAL_TEXT,
    relief="flat",
    borderwidth=0,
    highlightthickness=0,
    padx=12,
    pady=10,
    insertbackground=TERMINAL_PROMPT,
    selectbackground="#064e3b",
    selectforeground=TERMINAL_TEXT
)
msg_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
tk.Label(
    bottom_frame,
    text="Enter: Send  |  @send: Send  |  /clear: Clear Chat",
    bg=TERMINAL_BG,
    fg=TERMINAL_PROMPT,
    font=("Consolas", 9, "bold"),
    anchor="w",
    padx=12
).grid(row=1, column=0, sticky="ew", pady=(0, 8))

right_column = tk.Frame(content, bg=BG)
right_column.grid(row=0, column=2, sticky="nsew", padx=(12, 0))

actions_panel = make_panel(right_column, "QUICK ACTIONS", padding=10)
actions_panel.pack(fill="x")
actions = tk.Frame(actions_panel, bg=TERMINAL_BG)
actions.pack(fill="x", padx=10, pady=(16, 10))

send_btn = ttk.Button(
    bottom_frame,
    text="SEND [ENTER]",
    command=send_message,
    style="Success.TButton"
)
send_btn.grid(row=0, column=1, sticky="e", padx=(8, 12), pady=12)

status_panel = make_panel(right_column, "STATUS", padding=10)
status_panel.pack(fill="x", pady=(18, 0))
for label, value in (
    ("Network:", "Connected"),
    ("Sharing:", "Active"),
    ("Firewall:", "OK"),
    ("Encryption:", "Enabled"),
):
    row = tk.Frame(status_panel, bg=TERMINAL_BG)
    row.pack(fill="x", padx=12, pady=7)
    tk.Label(row, text=label, bg=TERMINAL_BG, fg=TERMINAL_TEXT, font=("Consolas", 10), width=12, anchor="w").pack(side="left")
    tk.Label(row, text=value, bg=TERMINAL_BG, fg=TERMINAL_PROMPT, font=("Consolas", 10, "bold"), anchor="w").pack(side="left")

footer = tk.Frame(main, bg=BG)
footer.pack(fill="x", pady=(12, 0))
tk.Label(
    footer,
    text=">> HubSync Terminal Edition v1.0.0",
    bg=BG,
    fg=TERMINAL_PROMPT,
    font=("Consolas", 9),
    anchor="w"
).pack(side="left")
tk.Label(
    footer,
    text=">> Secure   |   Fast   |   Local Network",
    bg=BG,
    fg=TERMINAL_TEXT,
    font=("Consolas", 9),
).pack(side="left", expand=True)


def open_emoji_picker():
    picker = tk.Toplevel(root)
    picker.title("Payload Snippets")
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
    text="Snippets",
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
    text="Purge Log",
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
    text="Share Dir",
    command=share_folder,
    style="Primary.TButton"
)
share_btn.pack(fill="x", pady=(8, 0))

stop_share_btn = ttk.Button(
    actions,
    text="Stop Share",
    command=stop_all_shares,
    style="Danger.TButton"
)
stop_share_btn.pack(fill="x", pady=(8, 0))


def on_ctrl_enter(event=None):
    send_message()
    return "break"


def on_message_input(event=None):
    message_text = msg_entry.get("1.0", tk.END).strip()

    if not message_text.endswith("@send"):
        return

    message_text = message_text[:-5].rstrip()
    msg_entry.delete("1.0", tk.END)

    if message_text:
        msg_entry.insert("1.0", message_text)
        send_message()


msg_entry.bind("<Control-Return>", on_ctrl_enter)
msg_entry.bind("<KeyRelease>", on_message_input)


def on_close():
    save_chat_histories()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.bind_all("<KeyPress>", reset_auto_lock_timer)
root.bind_all("<ButtonPress>", reset_auto_lock_timer)
root.bind_all("<MouseWheel>", reset_auto_lock_timer)
root.bind("<Unmap>", lock_when_minimized)

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
