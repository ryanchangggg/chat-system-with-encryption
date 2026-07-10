# Secure Chat System

A Python-based chat system with end-to-end encryption, supporting both a graphical (Tkinter) and command-line interface. Messages between peers are secured using Diffie-Hellman key exchange and AES-256-GCM encryption.

## Features

- **End-to-End Encryption**: Uses Diffie-Hellman key exchange (RFC 3526 2048-bit MODP group) to negotiate a shared secret, then encrypts all messages with AES-256-GCM.
- **Graphical GUI**: Built with Tkinter — login, chat, and control buttons for common commands.
- **Searchable Chat History**: Every message is indexed server-side; you can search past conversations.
- **Sonnet Retrieval**: Fetch any of Shakespeare's 154 sonnets by number.
- **Multi-User Support**: Multiple users can be logged in simultaneously; the server tracks who is online and in which chat groups.

## Quick Start

### Prerequisites

- Python 3.7+
- [cryptography](https://pypi.org/project/cryptography/) library (`pip install cryptography`)
- Tkinter (usually included with Python, but on some systems you may need to install it separately, e.g., `python3-tk` on Debian/Ubuntu)

### 1. Start the Server

```bash
python3 chat_server.py
```

The server listens on `127.0.0.1:1112` by default. You should see `starting server...` printed to the console.

### 2. Start a Client (GUI)

```bash
python3 chat_cmdl_client.py
```

If the server is on a different machine, use the `-d` flag to specify its IP address:

```bash
python3 chat_cmdl_client.py -d 192.168.1.100
```

### 3. Log In

Enter a username in the login window and click **CONTINUE** (or press Enter). The username must be unique — if someone else is already logged in with the same name, you will be prompted to try again.

## Commands

Once logged in, you can use the following commands via the text input or the sidebar buttons:

| Command | Button | Description |
|---------|--------|-------------|
| `time` | 🕐 Time | Show the current server time |
| `who` | 👥 Who | List all online users |
| `c <peer>` | 🔗 Connect | Connect to another user to start chatting |
| `? <term>` | 🔍 Search | Search your chat history for messages containing `<term>` |
| `p <#>` | 📜 Poem | Retrieve Shakespeare sonnet number `<#>` (1–154) |
| `bye` | 🔌 Disconnect | Disconnect from the current chat peer |
| `q` | 🚪 Logout | Log out and close the application |

### Chatting Flow

1. Log in with a unique username.
2. Both you and your partner should log in.
3. One of you types `c <partner_name>` (or clicks **Connect** and enters the name).
4. Once connected, the DH key exchange runs automatically in the background. You will see `[✓] Secure channel established` when encryption is active.
5. Type your message and press Enter or click **Send**. All messages are encrypted end-to-end.
6. Type `bye` or click **Disconnect** to end the conversation.
7. Type `q` or click **Logout** to leave the system.

## Project Structure

| File | Purpose |
|------|---------|
| `chat_server.py` | Server — handles client connections, message routing, chat indexing, and sonnet retrieval |
| `chat_cmdl_client.py` | Client entry point — parses arguments and launches the GUI |
| `chat_client_class.py` | Client class — connects to the server, manages the socket, and ties together the GUI and state machine |
| `GUI.py` | Tkinter-based graphical user interface with login window, chat display, and command buttons |
| `client_state_machine.py` | Client-side finite state machine — handles login, chatting, encrypted messaging, and the DH key exchange protocol |
| `chat_utils.py` | Shared utilities — socket send/recv with length prefix, state constants, and text formatting |
| `chat_group.py` | Group management — tracks online users and chat groups on the server |
| `crypto_utils.py` | Cryptographic primitives — Diffie-Hellman key generation, shared secret derivation, AES-256-GCM encryption/decryption |
| `indexer.py` | Message indexing and search — used for chat history lookup |
| `indexer_good.py` | Alternative version of the indexer (not used by the server) |
| `AllSonnets.txt` | Complete collection of Shakespeare's sonnets |
| `roman.txt.pk` | Pickled mapping of integers to Roman numerals (used to identify sonnet boundaries) |

## How Encryption Works

1. When two peers connect, each generates an ephemeral Diffie-Hellman key pair.
2. Both peers send their DH public key to the other (relayed through the server).
3. Each peer independently computes the shared secret using their private key and the peer's public key.
4. A 256-bit AES key is derived from the shared secret via SHA-256.
5. Every chat message is encrypted with AES-256-GCM before being sent through the server.
6. The server only ever sees DH public keys and encrypted ciphertext — it cannot read the messages.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Address already in use` when starting server | Wait a few seconds for the port to be released, or kill any lingering process: `lsof -ti:1112 \| xargs kill -9` |
| `ModuleNotFoundError: No module named 'cryptography'` | Install it: `pip install cryptography` |
| GUI does not open / Tkinter error | Install Tkinter: `apt install python3-tk` (Linux) or `brew install python-tk` (macOS) |
| Duplicate login error | Choose a different username |
| `[!] Failed to decrypt message` | The key exchange may not have completed yet. Wait a moment and try again. |
