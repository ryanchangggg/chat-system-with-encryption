from chat_utils import *
import json
from crypto_utils import (
    dh_generate_keypair,
    dh_compute_shared_secret,
    make_key_exchange_msg,
    is_key_exchange_msg,
    extract_public_key,
    encrypt_message,
    decrypt_message,
)

class ClientSM:
    def __init__(self, s):
        self.state = S_OFFLINE
        self.peer = ''
        self.me = ''
        self.out_msg = ''
        self.s = s

        # ----- secure messaging state -----
        self.shared_key = None          # 32-byte AES key (set after DH)
        self._dh_priv, self._dh_pub = dh_generate_keypair()
        self._key_sent    = False       # have we transmitted our public key?
        self._key_complete = False      # has the handshake finished?

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def set_myname(self, name):
        self.me = name

    def get_myname(self):
        return self.me

    def is_secure(self):
        """Return True once the DH key exchange has completed."""
        return self._key_complete

    def reset_key_exchange(self):
        """Reset crypto state so a new handshake can happen."""
        self.shared_key = None
        self._dh_priv, self._dh_pub = dh_generate_keypair()
        self._key_sent = False
        self._key_complete = False

    # ------------------------------------------------------------------
    # connection helpers
    # ------------------------------------------------------------------

    def connect_to(self, peer):
        msg = json.dumps({"action":"connect", "target":peer})
        mysend(self.s, msg)
        response = json.loads(myrecv(self.s))
        if response["status"] == "success":
            self.peer = peer
            self.out_msg += 'You are connected with '+ self.peer + '\n'
            self.reset_key_exchange()
            return True
        elif response["status"] == "busy":
            self.out_msg += 'User is busy. Please try again later\n'
        elif response["status"] == "self":
            self.out_msg += 'Cannot talk to yourself (sick)\n'
        else:
            self.out_msg += 'User is not online, try again later\n'
        return False

    def disconnect(self):
        msg = json.dumps({"action":"disconnect"})
        mysend(self.s, msg)
        self.out_msg += 'You are disconnected from ' + self.peer + '\n'
        self.peer = ''
        self.reset_key_exchange()

    # ------------------------------------------------------------------
    # main event processor
    # ------------------------------------------------------------------

    def proc(self, my_msg, peer_msg):
        self.out_msg = ''

        # ===== S_LOGGEDIN =============================================
        if self.state == S_LOGGEDIN:
            if len(my_msg) > 0:
                if my_msg == 'q':
                    self.out_msg += 'See you next time!\n'
                    self.state = S_OFFLINE

                elif my_msg == 'time':
                    mysend(self.s, json.dumps({"action":"time"}))
                    time_in = json.loads(myrecv(self.s))["results"]
                    self.out_msg += "Time is: " + time_in

                elif my_msg == 'who':
                    mysend(self.s, json.dumps({"action":"list"}))
                    logged_in = json.loads(myrecv(self.s))["results"]
                    self.out_msg += 'Here are all the users in the system:\n'
                    self.out_msg += logged_in

                elif my_msg[0] == 'c':
                    peer = my_msg[1:]
                    peer = peer.strip()
                    if self.connect_to(peer):
                        self.state = S_CHATTING
                        self.out_msg += 'Connect to ' + peer + '. Chat away!\n\n'
                        self.out_msg += '-----------------------------------\n'
                    else:
                        self.out_msg += 'Connection unsuccessful\n'

                elif my_msg[0] == '?':
                    term = my_msg[1:].strip()
                    mysend(self.s, json.dumps({"action":"search", "target":term}))
                    search_rslt = json.loads(myrecv(self.s))["results"].strip()
                    if len(search_rslt) > 0:
                        self.out_msg += search_rslt + '\n\n'
                    else:
                        self.out_msg += '\'' + term + '\' not found\n\n'

                elif my_msg[0] == 'p' and my_msg[1:].isdigit():
                    poem_idx = my_msg[1:].strip()
                    mysend(self.s, json.dumps({"action":"poem", "target":poem_idx}))
                    poem = json.loads(myrecv(self.s))["results"]
                    if len(poem) > 0:
                        self.out_msg += poem + '\n\n'
                    else:
                        self.out_msg += 'Sonnet ' + poem_idx + ' not found\n\n'
                else:
                    self.out_msg += menu

            if len(peer_msg) > 0:
                peer_data = json.loads(peer_msg)
                if peer_data["action"] == "connect":
                    self.peer = peer_data["from"]
                    self.out_msg += 'Request from ' + self.peer + '\n'
                    self.out_msg += 'You are connected with ' + self.peer
                    self.out_msg += '. Chat away!\n\n'
                    self.out_msg += '------------------------------------\n'
                    self.state = S_CHATTING
                    self.reset_key_exchange()

        # ===== S_CHATTING =============================================
        elif self.state == S_CHATTING:
            # --- Phase 1: DH key exchange (until shared_key is set) ----
            if not self._key_complete:
                self._handle_key_exchange(my_msg, peer_msg)

            # --- Phase 2: normal encrypted messaging -------------------
            else:
                # my outgoing message
                if len(my_msg) > 0:
                    encrypted = encrypt_message(self.shared_key, my_msg)
                    mysend(self.s, json.dumps({
                        "action": "exchange",
                        "from": "[" + self.me + "]",
                        "message": encrypted
                    }))
                    if my_msg == 'bye':
                        self.disconnect()
                        self.state = S_LOGGEDIN
                        self.peer = ''

                # peer incoming message
                if len(peer_msg) > 0:
                    peer_data = json.loads(peer_msg)
                    if peer_data["action"] == "connect":
                        self.out_msg += "(" + peer_data["from"] + " joined)\n"
                    elif peer_data["action"] == "disconnect":
                        self.out_msg += "(" + self.peer + " left)\n"
                        self.state = S_LOGGEDIN
                        self.reset_key_exchange()
                    else:
                        # decrypt the incoming message
                        try:
                            plain = decrypt_message(self.shared_key,
                                                    peer_data["message"])
                            self.out_msg += peer_data["from"] + plain
                        except Exception:
                            self.out_msg += "[!] Failed to decrypt message\n"

            # show menu again when returning to S_LOGGEDIN
            if self.state == S_LOGGEDIN:
                self.out_msg += menu

        # ===== invalid state ==========================================
        else:
            self.out_msg += 'How did you wind up here??\n'
            print_state(self.state)

        return self.out_msg

    # ------------------------------------------------------------------
    # DH key-exchange sub-protocol
    # ------------------------------------------------------------------

    def _handle_key_exchange(self, my_msg, peer_msg):
        """Run the DH handshake.  May be called repeatedly until complete."""

        # 1. Do we have a peer message containing a DH public key?
        if len(peer_msg) > 0:
            peer_data = json.loads(peer_msg)

            # Did the peer send us a key-exchange message?
            if is_key_exchange_msg(peer_data):
                peer_pub = extract_public_key(peer_data)

                # If we haven't sent our own key yet, do it now first.
                if not self._key_sent:
                    mysend(self.s,
                           json.dumps(make_key_exchange_msg(self._dh_pub)))
                    self._key_sent = True

                self.shared_key = dh_compute_shared_secret(self._dh_priv,
                                                           peer_pub)
                self._key_complete = True
                self.out_msg += "[✓] Secure channel established\n"
                return

        # 2. No peer key yet — send ours (once) and wait.
        if not self._key_sent:
            mysend(self.s,
                   json.dumps(make_key_exchange_msg(self._dh_pub)))
            self._key_sent = True
            self.out_msg += "[⋯] Establishing secure channel…\n"
            return

        # 3. We've sent our key but haven't received the peer's yet.
        self.out_msg += "[⋯] Waiting for peer to complete key exchange…\n"
