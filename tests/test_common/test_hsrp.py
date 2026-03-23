"""Tests for HSRP packet building and AES encryption."""

from __future__ import annotations

import json
import struct
import zlib

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Internal helpers re-used in tests (import private members for white-box testing)
from common.protocols.hsrp import (
    HEADER_FMT,
    HEADER_SIZE,
    MAGIC,
    HSRPCommand,
    _AES_KEY,
    _AES_IV,
    _decrypt,
    _encrypt,
)


class TestAesEncryption:
    """AES-128-CBC encrypt/decrypt round-trips."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        plaintext = b'{"task_id": "job-001"}'
        ciphertext = _encrypt(plaintext)
        recovered = _decrypt(ciphertext)
        assert recovered == plaintext

    def test_encrypt_produces_different_bytes(self) -> None:
        data = b"hello"
        assert _encrypt(data) != data

    def test_known_key_length(self) -> None:
        """Key must be exactly 16 bytes for AES-128."""
        assert len(_AES_KEY) == 16

    def test_known_iv_all_zeros(self) -> None:
        assert _AES_IV == b"\x00" * 16

    def test_decrypt_known_ciphertext(self) -> None:
        """Encrypt then decrypt a known payload and verify JSON round-trip."""
        payload = {"cmd": "test", "value": 42}
        raw = json.dumps(payload).encode("utf-8")
        cipher = _encrypt(raw)
        result = json.loads(_decrypt(cipher).decode("utf-8"))
        assert result["cmd"] == "test"
        assert result["value"] == 42

    def test_encrypted_length_is_multiple_of_16(self) -> None:
        """PKCS7 padding ensures output is always a multiple of block size."""
        for length in range(1, 50):
            ct = _encrypt(b"x" * length)
            assert len(ct) % 16 == 0


class TestHsrpPacketBuilding:
    """Validate header structure and CRC fields."""

    def _build_packet(self, cmd_id: int, payload_dict: dict) -> bytes:
        """Manually build a packet the same way HSRPClient.send_command does."""
        plaintext = json.dumps(payload_dict).encode("utf-8")
        ciphertext = _encrypt(plaintext)
        crc = zlib.crc32(plaintext) & 0xFFFFFFFF
        header = struct.pack(HEADER_FMT, MAGIC, cmd_id, 1, len(ciphertext), crc, 0)
        return header + ciphertext

    def test_header_size_is_24(self) -> None:
        assert HEADER_SIZE == 24

    def test_magic_bytes(self) -> None:
        assert MAGIC == b"HSRP"

    def test_packet_starts_with_magic(self) -> None:
        packet = self._build_packet(HSRPCommand.GET_PROGRESS, {"task_id": "t1"})
        assert packet[:4] == MAGIC

    def test_cmd_id_encoded_correctly(self) -> None:
        for cmd in (HSRPCommand.GET_PROGRESS, HSRPCommand.PRINT_TASK, HSRPCommand.RIP_IMPORT):
            packet = self._build_packet(cmd, {})
            _, cmd_read, *_ = struct.unpack(HEADER_FMT, packet[:HEADER_SIZE])
            assert cmd_read == cmd

    def test_crc_field_matches_plaintext(self) -> None:
        payload = {"test": True}
        plaintext = json.dumps(payload).encode("utf-8")
        packet = self._build_packet(HSRPCommand.CLEAN_HEAD, payload)
        _, _, _, plen, crc_field, _ = struct.unpack(HEADER_FMT, packet[:HEADER_SIZE])
        expected_crc = zlib.crc32(plaintext) & 0xFFFFFFFF
        assert crc_field == expected_crc

    def test_payload_length_field_matches_ciphertext_length(self) -> None:
        payload = {"task_id": "abc"}
        packet = self._build_packet(HSRPCommand.PRINT_TASK, payload)
        _, _, _, plen, _, _ = struct.unpack(HEADER_FMT, packet[:HEADER_SIZE])
        assert plen == len(packet) - HEADER_SIZE

    def test_command_constants(self) -> None:
        assert HSRPCommand.RIP_IMPORT == 21
        assert HSRPCommand.PRINT_TASK == 11
        assert HSRPCommand.GET_PROGRESS == 10
        assert HSRPCommand.CLEAN_HEAD == 14
