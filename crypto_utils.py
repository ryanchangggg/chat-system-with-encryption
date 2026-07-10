#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crypto_utils.py — Secure Messaging Module

Provides:
  - Diffie-Hellman key exchange (RFC 3526 2048-bit MODP group)
  - AES-256-GCM authenticated encryption via the `cryptography` library
  - Serialization helpers for DH public keys

The server sees only DH public keys (which reveal nothing about the shared
secret), so it cannot read the encrypted chat messages.
"""

import os
import base64
import secrets
import hashlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---------------------------------------------------------------------------
# Diffie-Hellman parameters  (RFC 3526, 2048-bit MODP Group)
# ---------------------------------------------------------------------------
DH_P = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
DH_G = 2


def dh_generate_keypair():
    """Return (private_key_int, public_key_int) for a new DH key pair."""
    private_key = int.from_bytes(secrets.token_bytes(256), "big") % DH_P
    public_key = pow(DH_G, private_key, DH_P)
    return private_key, public_key


def dh_compute_shared_secret(private_key, peer_public_key):
    """Derive a 32-byte AES-256 key from the DH shared secret via SHA-256."""
    shared = pow(peer_public_key, private_key, DH_P)
    shared_bytes = shared.to_bytes((shared.bit_length() + 7) // 8, "big")
    return hashlib.sha256(shared_bytes).digest()


# ---------------------------------------------------------------------------
# AES-256-GCM encryption / decryption
# ---------------------------------------------------------------------------

def encrypt_message(key, plaintext):
    """
    Encrypt *plaintext* (a str) with *key* (32 bytes) using AES-256-GCM.

    Returns a base64-encoded string that bundles the 12-byte nonce and the
    ciphertext (which includes the 16-byte GCM authentication tag).
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)                     # 96-bit nonce
    ciphertext = aesgcm.encrypt(
        nonce, plaintext.encode("utf-8"), None
    )
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_message(key, encrypted_data):
    """
    Decrypt a base64-encoded payload produced by *encrypt_message*.

    Returns the original plaintext string, or raises an exception if the
    authentication tag is invalid (tampered data / wrong key).
    """
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted_data)
    nonce = raw[:12]
    ciphertext = raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


# ---------------------------------------------------------------------------
# Convenience helpers for JSON-serializable key exchange
# ---------------------------------------------------------------------------

def make_key_exchange_msg(public_key):
    """Build a JSON-ready dict that carries the caller's DH public key."""
    return {"action": "key_exchange", "public_key": str(public_key)}


def is_key_exchange_msg(msg):
    """Return True if *msg* (a parsed dict) is a key-exchange message."""
    return isinstance(msg, dict) and msg.get("action") == "key_exchange"


def extract_public_key(msg):
    """Extract the integer public key from a key-exchange dict."""
    return int(msg["public_key"])
