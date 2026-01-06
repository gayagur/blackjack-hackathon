"""
Constants for Blackjack Client-Server Game

This module contains all protocol, game result, network, and card display
constants used throughout the networked Blackjack game implementation.
"""

# ============================================================================
# Protocol Constants
# ============================================================================

# Magic cookie value used to validate all packets in the protocol
# All valid packets must start with this value
MAGIC_COOKIE = 0xabcddcba

# Message type: Server broadcasts this to discover available clients
MSG_TYPE_OFFER = 0x02

# Message type: Client sends this to request joining a game
MSG_TYPE_REQUEST = 0x03

# Message type: Contains game data such as cards and player decisions
MSG_TYPE_PAYLOAD = 0x04


# ============================================================================
# Game Result Constants
# ============================================================================

# Round is still in progress, no result yet
RESULT_NOT_OVER = 0x00

# Round ended in a tie (push)
RESULT_TIE = 0x01

# Client lost the round
RESULT_LOSS = 0x02

# Client won the round
RESULT_WIN = 0x03


# ============================================================================
# Network Constants
# ============================================================================

# UDP port number on which clients listen for server broadcast messages
UDP_BROADCAST_PORT = 13122

# Team name identifier (change this to your actual team name)
TEAM_NAME = "Yoske"


# ============================================================================
# Game Mode Constants
# ============================================================================

# Game Modes
MODE_CLASSIC = 1
MODE_CASINO = 2
MODE_BOT = 3

# Casino Mode Settings
STARTING_CHIPS = 1000
MIN_BET = 10
MAX_BET = 500
BLACKJACK_MULTIPLIER = 1.5  # Blackjack pays 3:2
DOUBLE_DOWN_ENABLED = True


# ============================================================================
# Card Display Constants
# ============================================================================

# Dictionary mapping suit values to their Unicode symbols
# Used for displaying cards in a human-readable format
SUITS = {
    0: '♥',  # Heart
    1: '♦',  # Diamond
    2: '♣',  # Club
    3: '♠'   # Spade
}

# Dictionary mapping rank values to their display strings
# Used for displaying card ranks in a human-readable format
RANKS = {
    1: 'A',   # Ace
    2: '2',
    3: '3',
    4: '4',
    5: '5',
    6: '6',
    7: '7',
    8: '8',
    9: '9',
    10: '10',
    11: 'J',  # Jack
    12: 'Q',  # Queen
    13: 'K'   # King
}

