#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI.py — Tkinter-based chat client GUI with action buttons and secure messaging.

Provides:
  - Login window (enter username)
  - Main chat window with:
      * Scrollable message display
      * Text input + Send button
      * Buttons: Time, Who, Poem, Search, Connect, Disconnect, Logout
  - Background thread to receive unsolicited peer messages
  - Full integration with the client state machine and secure messaging
"""

import threading
import select
import json
import queue
from tkinter import *
from tkinter import font
from tkinter import scrolledtext, simpledialog, messagebox

from chat_utils import *
import client_state_machine as csm


class GUI:
    """Main GUI class for the chat client."""

    def __init__(self, send, recv, sm, s):
        self.send = send          # sends bytes on the socket
        self.recv = recv          # receives bytes from the socket
        self.sm = sm              # ClientSM instance
        self.socket = s

        # Queues that bridge the UI thread and the background reader thread
        self.my_msg_queue = queue.Queue()
        self.peer_msg_queue = queue.Queue()
        self._stop_thread = False

        # Top-level window (hidden until login succeeds)
        self.Window = Tk()
        self.Window.withdraw()
        self.Window.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ==================================================================
    # LOGIN WINDOW
    # ==================================================================

    def login(self):
        self.login = Toplevel()
        self.login.title("Login")
        self.login.resizable(width=False, height=False)
        self.login.configure(width=400, height=250)

        Label(self.login, text="Please login to continue",
              justify=CENTER, font="Helvetica 14 bold")\
            .place(relheight=0.15, relx=0.2, rely=0.07)

        Label(self.login, text="Name: ", font="Helvetica 12")\
            .place(relheight=0.2, relx=0.1, rely=0.2)

        self.entryName = Entry(self.login, font="Helvetica 14")
        self.entryName.place(relwidth=0.4, relheight=0.12,
                             relx=0.35, rely=0.2)
        self.entryName.focus()
        self.entryName.bind("<Return>",
                            lambda e: self.goAhead(self.entryName.get()))

        Button(self.login, text="CONTINUE", font="Helvetica 14 bold",
               command=lambda: self.goAhead(self.entryName.get()))\
            .place(relx=0.4, rely=0.55)

        self.Window.mainloop()

    def goAhead(self, name):
        name = name.strip()
        if len(name) == 0:
            return
        msg = json.dumps({"action": "login", "name": name})
        self.send(msg)
        response = json.loads(self.recv())
        if response["status"] == 'ok':
            self.login.destroy()
            self.sm.set_state(S_LOGGEDIN)
            self.sm.set_myname(name)
            self.build_layout(name)
            self.display_message(menu + "\n")
            # Start the background reader thread
            self._stop_thread = False
            reader = threading.Thread(target=self._reader_loop, daemon=True)
            reader.start()
            # Start the periodic poller that checks the queues
            self.Window.after(100, self._poll_queues)
        else:
            messagebox.showerror("Login failed",
                                 "Duplicate name or server error. Try again.")

    # ==================================================================
    # MAIN CHAT LAYOUT
    # ==================================================================

    def build_layout(self, name):
        self.name = name
        self.Window.deiconify()
        self.Window.title("Secure Chat — " + name)
        self.Window.resizable(width=True, height=True)
        self.Window.minsize(680, 520)
        self.Window.configure(bg="#17202A")

        # ---------- title bar ----------
        title = Label(self.Window, bg="#17202A", fg="#EAECEE",
                      text="Secure Chat [" + name + "]",
                      font="Helvetica 14 bold", pady=5)
        title.pack(fill=X)

        sep = Frame(self.Window, height=2, bg="#ABB2B9")
        sep.pack(fill=X, padx=5)

        # ---------- main area: text display + button panel ----------
        main_frame = Frame(self.Window, bg="#17202A")
        main_frame.pack(fill=BOTH, expand=True, padx=5, pady=(2, 5))

        # text display area (left ~75 %)
        self.textCons = scrolledtext.ScrolledText(
            main_frame,
            wrap=WORD,
            state=DISABLED,
            bg="#17202A", fg="#EAECEE",
            font="Helvetica 13",
            padx=8, pady=5,
            relief=FLAT,
            borderwidth=0,
            highlightthickness=0,
        )
        self.textCons.pack(side=LEFT, fill=BOTH, expand=True)

        # ---------- right button panel ----------
        btn_frame = Frame(main_frame, bg="#17202A", width=150)
        btn_frame.pack(side=RIGHT, fill=Y, padx=(8, 0))
        btn_frame.pack_propagate(False)

        btn_font = "Helvetica 11 bold"

        def mkbtn(text, cmd, color="#ABB2B9"):
            return Button(btn_frame, text=text, font=btn_font,
                          bg=color, fg="#17202A",
                          command=cmd,
                          relief=RAISED, borderwidth=2)

        # Time button
        mkbtn("🕐 Time", self.cmd_time)\
            .pack(fill=X, pady=3, ipady=4)
        # Who button
        mkbtn("👥 Who", self.cmd_who)\
            .pack(fill=X, pady=3, ipady=4)
        # Poem button
        mkbtn("📜 Poem", self.cmd_poem)\
            .pack(fill=X, pady=3, ipady=4)
        # Search button
        mkbtn("🔍 Search", self.cmd_search)\
            .pack(fill=X, pady=3, ipady=4)
        # Separator
        Frame(btn_frame, bg="#ABB2B9", height=2).pack(fill=X, pady=6)
        # Connect button
        mkbtn("🔗 Connect", self.cmd_connect, color="#A9DFBF")\
            .pack(fill=X, pady=3, ipady=4)
        # Disconnect button
        mkbtn("🔌 Disconnect", self.cmd_disconnect, color="#F5B7B1")\
            .pack(fill=X, pady=3, ipady=4)
        # Logout button
        mkbtn("🚪 Logout", self.cmd_logout, color="#FAD7A0")\
            .pack(fill=X, pady=3, ipady=4)

        # ---------- bottom bar: input + send ----------
        bottom_bar = Frame(self.Window, bg="#ABB2B9", height=50)
        bottom_bar.pack(fill=X, side=BOTTOM)
        bottom_bar.pack_propagate(False)

        self.entryMsg = Entry(bottom_bar,
                              bg="#2C3E50", fg="#EAECEE",
                              font="Helvetica 13",
                              relief=FLAT, borderwidth=3)
        self.entryMsg.place(relx=0.01, rely=0.12,
                            relwidth=0.78, relheight=0.76)
        self.entryMsg.focus()
        self.entryMsg.bind("<Return>", lambda e: self.send_button())

        self.send_btn = Button(bottom_bar,
                               text="Send", font="Helvetica 11 bold",
                               bg="#5D6D7E", fg="#EAECEE",
                               command=self.send_button,
                               relief=RAISED, borderwidth=2)
        self.send_btn.place(relx=0.81, rely=0.12,
                            relwidth=0.17, relheight=0.76)

    # ==================================================================
    # COMMAND BUTTON HANDLERS
    # ==================================================================

    def cmd_time(self):
        """Send the 'time' command to the state machine."""
        self.my_msg_queue.put("time")

    def cmd_who(self):
        """Send the 'who' command to list online users."""
        self.my_msg_queue.put("who")

    def cmd_poem(self):
        """Prompt for a sonnet number, then fetch it."""
        num = simpledialog.askstring("Poem", "Sonnet number (1–154):",
                                     parent=self.Window)
        if num and num.strip().isdigit():
            self.my_msg_queue.put("p" + num.strip())

    def cmd_search(self):
        """Prompt for a search term, then search chat history."""
        term = simpledialog.askstring("Search",
                                      "Search chat history for:",
                                      parent=self.Window)
        if term and len(term.strip()) > 0:
            self.my_msg_queue.put("?" + term.strip())

    def cmd_connect(self):
        """Prompt for a peer name, then connect."""
        peer = simpledialog.askstring("Connect",
                                      "Enter peer name to connect:",
                                      parent=self.Window)
        if peer and len(peer.strip()) > 0:
            self.my_msg_queue.put("c" + peer.strip())

    def cmd_disconnect(self):
        """Disconnect from current peer."""
        self.my_msg_queue.put("bye")

    def cmd_logout(self):
        """Log out and close."""
        self.my_msg_queue.put("q")

    def send_button(self):
        """Send whatever is in the text entry field."""
        msg = self.entryMsg.get().strip()
        if len(msg) > 0:
            self.my_msg_queue.put(msg)
            self.entryMsg.delete(0, END)

    # ==================================================================
    # BACKGROUND READER THREAD
    # ==================================================================

    def _reader_loop(self):
        """Runs in a daemon thread; reads peer messages from the socket
        and pushes them into peer_msg_queue."""
        while not self._stop_thread:
            try:
                read, _, _ = select.select([self.socket], [], [], 0.2)
                if self.socket in read:
                    peer_msg = self.recv()
                    if len(peer_msg) > 0:
                        self.peer_msg_queue.put(peer_msg)
                    else:
                        # socket closed
                        break
            except Exception:
                break

    # ==================================================================
    # QUEUE POLLER (runs on the main thread via .after())
    # ==================================================================

    def _poll_queues(self):
        """Called every 100 ms from the main thread.  Drains both queues
        and feeds them to the state machine, then updates the display."""
        if self._stop_thread:
            return

        # Collect all pending my-messages (from button clicks / Send)
        my_msg = ""
        while not self.my_msg_queue.empty():
            try:
                part = self.my_msg_queue.get_nowait()
                my_msg = part  # take the most recent one
            except queue.Empty:
                break

        # Collect all pending peer-messages
        peer_msg = ""
        while not self.peer_msg_queue.empty():
            try:
                peer_msg = self.peer_msg_queue.get_nowait()
            except queue.Empty:
                break

        if len(my_msg) > 0 or len(peer_msg) > 0:
            result = self.sm.proc(my_msg, peer_msg)
            if len(result) > 0:
                self.display_message(result)

        self.Window.after(100, self._poll_queues)

    # ==================================================================
    # DISPLAY HELPER
    # ==================================================================

    def display_message(self, text):
        """Insert *text* at the end of the chat display (thread-safe)."""
        self.textCons.config(state=NORMAL)
        self.textCons.insert(END, text)
        self.textCons.see(END)
        self.textCons.config(state=DISABLED)

    # ==================================================================
    # CLEANUP
    # ==================================================================

    def on_closing(self):
        """Handle window close button."""
        if messagebox.askokcancel("Quit", "Do you want to leave the chat?"):
            self._stop_thread = True
            try:
                self.send(json.dumps({"action": "disconnect"}))
            except Exception:
                pass
            self.Window.destroy()

    def run(self):
        self.login()
