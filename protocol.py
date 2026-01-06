"""
Protocol module for Blackjack Client-Server Game

This module provides functions to pack and unpack network packets
using the struct module for the Blackjack game protocol.
"""

import struct
from constants import (
    MAGIC_COOKIE,
    MSG_TYPE_OFFER,
    MSG_TYPE_REQUEST,
    MSG_TYPE_PAYLOAD
)


def create_offer_packet(tcp_port: int, server_name: str) -> bytes:
    """
    Create an offer packet for UDP broadcast.
    
    Packet format: >IB H 32s (39 bytes total)
    - Magic Cookie: 4 bytes (0xabcddcba)
    - Message Type: 1 byte (0x02)
    - TCP Port: 2 bytes
    - Server Name: 32 bytes (padded with 0x00 if shorter)
    
    Args:
        tcp_port: The server's TCP port number
        server_name: The server name (will be truncated/padded to 32 bytes)
    
    Returns:
        bytes: The packed offer packet
    """
    # Encode server name and pad/truncate to exactly 32 bytes
    name_bytes = server_name.encode('utf-8')[:32]
    name_bytes = name_bytes.ljust(32, b'\x00')
    
    # Pack the packet: big-endian, unsigned int (4), unsigned char (1), unsigned short (2), 32-byte string
    packet = struct.pack('>IB H 32s', MAGIC_COOKIE, MSG_TYPE_OFFER, tcp_port, name_bytes)
    return packet


def parse_offer_packet(data: bytes) -> tuple | None:
    """
    Parse offer packet, return (tcp_port, server_name) or None if invalid.
    
    Args:
        data: The raw packet bytes to parse
    
    Returns:
        tuple: (tcp_port, server_name) if valid, None otherwise
    """
    try:
        # Check minimum size
        if len(data) < 39:
            return None
        
        # Unpack the packet
        magic_cookie, message_type, tcp_port, name_bytes = struct.unpack('>IB H 32s', data)
        
        # Validate magic cookie
        if magic_cookie != MAGIC_COOKIE:
            return None
        
        # Validate message type
        if message_type != MSG_TYPE_OFFER:
            return None
        
        # Decode server name and strip null bytes
        server_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='ignore')
        
        return (tcp_port, server_name)
    
    except (struct.error, UnicodeDecodeError):
        return None


def create_request_packet(num_rounds: int, client_name: str) -> bytes:
    """
    Create a request packet to join the game.
    
    Packet format: >IB B 32s (38 bytes total)
    - Magic Cookie: 4 bytes (0xabcddcba)
    - Message Type: 1 byte (0x03)
    - Number of Rounds: 1 byte (1-255)
    - Client Name: 32 bytes (padded with 0x00 if shorter)
    
    Args:
        num_rounds: Number of rounds to play (1-255)
        client_name: The client name (will be truncated/padded to 32 bytes)
    
    Returns:
        bytes: The packed request packet
    """
    # Validate num_rounds range
    if num_rounds < 1 or num_rounds > 255:
        raise ValueError("num_rounds must be between 1 and 255")
    
    # Encode client name and pad/truncate to exactly 32 bytes
    name_bytes = client_name.encode('utf-8')[:32]
    name_bytes = name_bytes.ljust(32, b'\x00')
    
    # Pack the packet: big-endian, unsigned int (4), unsigned char (1), unsigned char (1), 32-byte string
    packet = struct.pack('>IB B 32s', MAGIC_COOKIE, MSG_TYPE_REQUEST, num_rounds, name_bytes)
    return packet


def parse_request_packet(data: bytes) -> tuple | None:
    """
    Parse request packet, return (num_rounds, client_name) or None if invalid.
    
    Args:
        data: The raw packet bytes to parse
    
    Returns:
        tuple: (num_rounds, client_name) if valid, None otherwise
    """
    try:
        # Check minimum size
        if len(data) < 38:
            return None
        
        # Unpack the packet
        magic_cookie, message_type, num_rounds, name_bytes = struct.unpack('>IB B 32s', data)
        
        # Validate magic cookie
        if magic_cookie != MAGIC_COOKIE:
            return None
        
        # Validate message type
        if message_type != MSG_TYPE_REQUEST:
            return None
        
        # Validate num_rounds range
        if num_rounds < 1 or num_rounds > 255:
            return None
        
        # Decode client name and strip null bytes
        client_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='ignore')
        
        return (num_rounds, client_name)
    
    except (struct.error, UnicodeDecodeError):
        return None


def create_payload_client(decision: str) -> bytes:
    """
    Create client payload with decision ('Hittt' or 'Stand').
    
    Packet format: >IB 5s (10 bytes total)
    - Magic Cookie: 4 bytes (0xabcddcba)
    - Message Type: 1 byte (0x04)
    - Decision: 5 bytes ("Hittt" or "Stand")
    
    Args:
        decision: The player's decision, must be "Hittt" or "Stand"
    
    Returns:
        bytes: The packed client payload packet
    """
    # Validate decision
    if decision not in ("Hittt", "Stand"):
        raise ValueError("decision must be 'Hittt' or 'Stand'")
    
    # Encode decision and pad/truncate to exactly 5 bytes
    decision_bytes = decision.encode('utf-8')[:5]
    decision_bytes = decision_bytes.ljust(5, b'\x00')
    
    # Pack the packet: big-endian, unsigned int (4), unsigned char (1), 5-byte string
    packet = struct.pack('>IB 5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)
    return packet


def parse_payload_client(data: bytes) -> str | None:
    """
    Parse client payload, return decision string or None if invalid.
    
    Args:
        data: The raw packet bytes to parse
    
    Returns:
        str: The decision string ("Hittt" or "Stand") if valid, None otherwise
    """
    try:
        # Check minimum size
        if len(data) < 10:
            return None
        
        # Unpack the packet
        magic_cookie, message_type, decision_bytes = struct.unpack('>IB 5s', data)
        
        # Validate magic cookie
        if magic_cookie != MAGIC_COOKIE:
            return None
        
        # Validate message type
        if message_type != MSG_TYPE_PAYLOAD:
            return None
        
        # Decode decision and strip null bytes
        decision = decision_bytes.rstrip(b'\x00').decode('utf-8', errors='ignore')
        
        # Validate decision is one of the expected values
        if decision not in ("Hittt", "Stand"):
            return None
        
        return decision
    
    except (struct.error, UnicodeDecodeError):
        return None


def create_payload_server(result: int, card_rank: int, card_suit: int) -> bytes:
    """
    Create server payload with result and card info.
    
    Packet format: >IB B H B (9 bytes total)
    - Magic Cookie: 4 bytes (0xabcddcba)
    - Message Type: 1 byte (0x04)
    - Result: 1 byte (0=not over, 1=tie, 2=loss, 3=win)
    - Card Rank: 2 bytes (1-13: 1=Ace, 11=J, 12=Q, 13=K)
    - Card Suit: 1 byte (0-3: Heart, Diamond, Club, Spade)
    
    Args:
        result: Game result (0-3)
        card_rank: Card rank (1-13)
        card_suit: Card suit (0-3)
    
    Returns:
        bytes: The packed server payload packet
    """
    # Validate result range
    if result < 0 or result > 3:
        raise ValueError("result must be between 0 and 3")
    
    # Validate card_rank range
    if card_rank < 1 or card_rank > 13:
        raise ValueError("card_rank must be between 1 and 13")
    
    # Validate card_suit range
    if card_suit < 0 or card_suit > 3:
        raise ValueError("card_suit must be between 0 and 3")
    
    # Pack the packet: big-endian, unsigned int (4), unsigned char (1), unsigned char (1), unsigned short (2), unsigned char (1)
    packet = struct.pack('>IB B H B', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, result, card_rank, card_suit)
    return packet


def parse_payload_server(data: bytes) -> tuple | None:
    """
    Parse server payload, return (result, card_rank, card_suit) or None if invalid.
    
    Args:
        data: The raw packet bytes to parse
    
    Returns:
        tuple: (result, card_rank, card_suit) if valid, None otherwise
    """
    try:
        # Check minimum size
        if len(data) < 9:
            return None
        
        # Unpack the packet
        magic_cookie, message_type, result, card_rank, card_suit = struct.unpack('>IB B H B', data)
        
        # Validate magic cookie
        if magic_cookie != MAGIC_COOKIE:
            return None
        
        # Validate message type
        if message_type != MSG_TYPE_PAYLOAD:
            return None
        
        # Validate result range
        if result < 0 or result > 3:
            return None
        
        # Validate card_rank range
        if card_rank < 1 or card_rank > 13:
            return None
        
        # Validate card_suit range
        if card_suit < 0 or card_suit > 3:
            return None
        
        return (result, card_rank, card_suit)
    
    except (struct.error, UnicodeDecodeError):
        return None

