"""
Game Logic module for Blackjack Client-Server Game

This module provides Card and Deck classes, along with helper functions
for calculating hand values and determining game outcomes in Blackjack.
"""

import random
from constants import SUITS, RANKS


class Card:
    """
    Represents a single playing card in a Blackjack game.
    
    Attributes:
        rank: Card rank (1-13, where 1=Ace, 11=Jack, 12=Queen, 13=King)
        suit: Card suit (0-3, where 0=Heart, 1=Diamond, 2=Club, 3=Spade)
    """
    
    def __init__(self, rank: int, suit: int):
        """
        Initialize a card with rank and suit.
        
        Args:
            rank: 1-13 (1=Ace, 2-10=number, 11=Jack, 12=Queen, 13=King)
            suit: 0-3 (0=Heart, 1=Diamond, 2=Club, 3=Spade)
        """
        if rank < 1 or rank > 13:
            raise ValueError("rank must be between 1 and 13")
        if suit < 0 or suit > 3:
            raise ValueError("suit must be between 0 and 3")
        
        self.rank = rank
        self.suit = suit
    
    def get_value(self) -> int:
        """
        Return the blackjack value of this card.
        
        Returns:
            int: Card value
            - Ace (rank 1) = 11 points
            - Number cards (rank 2-10) = face value
            - Face cards (rank 11-13) = 10 points
        """
        if self.rank == 1:  # Ace
            return 11
        elif 2 <= self.rank <= 10:  # Number cards
            return self.rank
        else:  # Face cards (Jack, Queen, King)
            return 10
    
    def __str__(self) -> str:
        """
        Return a nice string representation of the card.
        
        Returns:
            str: Card representation like "K♠" or "7♥"
        """
        rank_str = RANKS.get(self.rank, str(self.rank))
        suit_str = SUITS.get(self.suit, '?')
        return f"{rank_str}{suit_str}"
    
    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return self.__str__()


class Deck:
    """
    Represents a deck of 52 playing cards for Blackjack.
    
    The deck is automatically shuffled upon creation and can be reset/shuffled
    again using the reset() method.
    """
    
    def __init__(self):
        """Create a new shuffled deck of 52 cards."""
        self.cards = []
        self.reset()
    
    def reset(self):
        """Reset and shuffle the deck with all 52 cards."""
        # Create a full deck: 13 ranks × 4 suits = 52 cards
        self.cards = []
        for suit in range(4):  # 0-3 for all suits
            for rank in range(1, 14):  # 1-13 for all ranks
                self.cards.append(Card(rank, suit))
        
        # Shuffle the deck
        random.shuffle(self.cards)
    
    def draw(self) -> Card:
        """
        Draw and return the top card from the deck.
        
        Returns:
            Card: The top card from the deck
        
        Raises:
            IndexError: If the deck is empty
        """
        if len(self.cards) == 0:
            raise IndexError("Cannot draw from empty deck")
        
        return self.cards.pop()
    
    def __len__(self) -> int:
        """
        Return number of cards remaining in the deck.
        
        Returns:
            int: Number of cards left
        """
        return len(self.cards)


def calculate_hand_value(cards: list) -> int:
    """
    Calculate the total value of a hand (list of Card objects).
    
    According to specification: Ace ALWAYS equals 11 points.
    No conversion to 1 is performed.
    
    Args:
        cards: List of Card objects representing the hand
    
    Returns:
        int: Total hand value (Aces always counted as 11)
    """
    if not cards:
        return 0
    
    # Sum all card values - Ace is always 11 according to spec
    total = sum(card.get_value() for card in cards)
    
    return total


def is_bust(cards: list) -> bool:
    """
    Return True if hand value exceeds 21 (bust).
    
    Args:
        cards: List of Card objects representing the hand
    
    Returns:
        bool: True if hand value > 21, False otherwise
    """
    return calculate_hand_value(cards) > 21


def format_hand(cards: list) -> str:
    """
    Return a formatted string showing all cards and total value.
    
    Args:
        cards: List of Card objects representing the hand
    
    Returns:
        str: Formatted string like "7♥ K♠ (17)" or "A♠ 5♦ (16)"
    """
    if not cards:
        return "Empty hand (0)"
    
    # Create string of all cards separated by spaces
    cards_str = " ".join(str(card) for card in cards)
    
    # Calculate total value
    total = calculate_hand_value(cards)
    
    return f"{cards_str} ({total})"

