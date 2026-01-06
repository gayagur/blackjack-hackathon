"""
Client module for Blackjack Client-Server Game

This module implements the Blackjack player/client that:
- Listens for UDP offers from servers
- Connects to servers and plays rounds of Blackjack
- Provides interactive user interface for game decisions
"""

import socket
import time
from constants import (
    UDP_BROADCAST_PORT,
    TEAM_NAME,
    RESULT_NOT_OVER,
    RESULT_TIE,
    RESULT_LOSS,
    RESULT_WIN,
    SUITS,
    RANKS
)
from protocol import (
    parse_offer_packet,
    create_request_packet,
    parse_payload_server,
    create_payload_client
)
from game_logic import (
    Card,
    calculate_hand_value,
    is_bust,
    format_hand
)

# Color constants
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"


# ============================================================================
# Visual Helper Functions
# ============================================================================

def clear_screen():
    """Clear the terminal screen"""
    print("\033[2J\033[H", end="")


def get_card_art(card: Card, hidden: bool = False):
    """
    Returns list of strings representing card ASCII art.
    
    Args:
        card: Card object
        hidden: If True, return hidden card art
    
    Returns:
        list: List of strings representing the card
    """
    if hidden:
        return [
            "┌─────────┐",
            "│░░░░░░░░░│",
            "│░░░░░░░░░│",
            "│░░░░░░░░░│",
            "│░░░░░░░░░│",
            "│░░░░░░░░░│",
            "└─────────┘"
        ]
    
    rank_str = RANKS.get(card.rank, str(card.rank))
    suit_str = SUITS.get(card.suit, '?')
    
    # Determine suit color (red for hearts/diamonds, white for clubs/spades)
    if card.suit in (0, 1):  # Heart or Diamond
        suit_color = RED
    else:  # Club or Spade
        suit_color = RESET
    
    # Pad rank for alignment
    if len(rank_str) == 2:  # "10"
        r = rank_str
        r_right = rank_str
    else:  # Single character
        r = rank_str + " "
        r_right = " " + rank_str
    
    return [
        "┌─────────┐",
        f"│ {r}      │",
        "│         │",
        f"│    {suit_color}{suit_str}{RESET}    │",
        "│         │",
        f"│      {r_right} │",
        "└─────────┘"
    ]


def print_cards_side_by_side(cards: list, hidden_count: int = 0, indent: int = 5):
    """
    Print multiple cards side by side.
    
    Args:
        cards: List of Card objects
        hidden_count: Number of hidden cards to show at the end
        indent: Number of spaces to indent (default 5 for box alignment)
    """
    card_arts = []
    
    # Add visible cards
    for card in cards:
        card_arts.append(get_card_art(card))
    
    # Add hidden cards
    for _ in range(hidden_count):
        card_arts.append(get_card_art(None, hidden=True))
    
    if not card_arts:
        return
    
    # All cards have same height (7 lines)
    height = len(card_arts[0])
    
    for row in range(height):
        line = "  ".join(card_art[row] for card_art in card_arts)
        print(f"{' ' * indent}{line}")


def print_welcome():
    """Print beautiful welcome screen"""
    print(f"\n{MAGENTA}")
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║     ███████╗██╗      █████╗  ██████╗██╗  ██╗     ██╗ █████╗  ██████╗██╗  ██╗   ║
    ║     ██╔══██║██║     ██╔══██╗██╔════╝██║ ██╔╝     ██║██╔══██╗██╔════╝██║ ██╔╝   ║
    ║     ███████║██║     ███████║██║     █████╔╝      ██║███████║██║     █████╔╝    ║
    ║     ██╔══██║██║     ██╔══██║██║     ██╔═██╗ ██   ██║██╔══██║██║     ██╔═██╗    ║
    ║     ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗╚█████╔╝██║  ██║╚██████╗██║  ██╗   ║
    ║     ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝   ║
    ║                                                                   ║
    ║                  ♠ ♥ ♣ ♦  WELCOME TO THE CASINO  ♦ ♣ ♥ ♠                  ║
    ║                                                                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    print(f"{RESET}\n")


def print_box(title: str, content: list, color: str = MAGENTA):
    """
    Print content in a nice box.
    
    Args:
        title: Box title
        content: List of content lines
        color: Color for the box
    """
    width = 60
    print(f"\n{color}╔{'═' * width}╗{RESET}")
    print(f"{color}║{title.center(width)}║{RESET}")
    print(f"{color}╠{'═' * width}╣{RESET}")
    print(f"{color}║{' ' * width}║{RESET}")
    
    for line in content:
        # Truncate if too long
        if len(line) > width - 4:
            line = line[:width - 7] + "..."
        print(f"{color}║{RESET}  {line.ljust(width - 4)}{color}║{RESET}")
    
    print(f"{color}║{' ' * width}║{RESET}")
    print(f"{color}╚{'═' * width}╝{RESET}\n")


def print_result_screen(result: int, player_value: int, dealer_value: int, player_bust: bool = False, dealer_bust: bool = False):
    """
    Print the win/lose/tie/bust screen.
    
    Args:
        result: RESULT_WIN, RESULT_LOSS, or RESULT_TIE
        player_value: Player's hand value
        dealer_value: Dealer's hand value
        player_bust: True if player busted
        dealer_bust: True if dealer busted
    """
    width = 60
    
    if player_bust:
        print(f"\n{RED}╔{'═' * width}╗{RESET}")
        print(f"{RED}║{' ' * width}║{RESET}")
        print(f"{RED}║{'💥 B U S T ! 💥   You went over 21!'.center(width)}║{RESET}")
        print(f"{RED}║{' ' * width}║{RESET}")
        print(f"{RED}║{f'Your hand: {player_value}'.center(width)}║{RESET}")
        print(f"{RED}║{' ' * width}║{RESET}")
        print(f"{RED}╚{'═' * width}╝{RESET}\n")
        return
    
    if dealer_bust:
        print(f"\n{GREEN}╔{'═' * width}╗{RESET}")
        print(f"{GREEN}║{' ' * width}║{RESET}")
        print(f"{GREEN}║{'🎉 DEALER BUSTS! 🎉   Dealer went over 21!'.center(width)}║{RESET}")
        print(f"{GREEN}║{' ' * width}║{RESET}")
        print(f"{GREEN}║{f'Dealer\'s hand: {dealer_value}  |  You WIN!'.center(width)}║{RESET}")
        print(f"{GREEN}║{' ' * width}║{RESET}")
        print(f"{GREEN}╚{'═' * width}╝{RESET}\n")
        return
    
    if result == RESULT_WIN:
        print(f"\n{GREEN}╔{'═' * width}╗{RESET}")
        print(f"{GREEN}║{' ' * width}║{RESET}")
        print(f"{GREEN}║{'🎉🎉🎉   Y O U   W I N !   🎉🎉🎉'.center(width)}║{RESET}")
        print(f"{GREEN}║{' ' * width}║{RESET}")
        print(f"{GREEN}║{f'Your hand: {player_value}  |  Dealer: {dealer_value}'.center(width)}║{RESET}")
        print(f"{GREEN}║{' ' * width}║{RESET}")
        print(f"{GREEN}║{' ' * 20}+ 1 WIN{' ' * 30}║{RESET}")
        print(f"{GREEN}║{' ' * width}║{RESET}")
        print(f"{GREEN}╚{'═' * width}╝{RESET}\n")
    elif result == RESULT_LOSS:
        print(f"\n{RED}╔{'═' * width}╗{RESET}")
        print(f"{RED}║{' ' * width}║{RESET}")
        print(f"{RED}║{'😞😞😞   Y O U   L O S E   😞😞😞'.center(width)}║{RESET}")
        print(f"{RED}║{' ' * width}║{RESET}")
        print(f"{RED}║{f'Your hand: {player_value}  |  Dealer: {dealer_value}'.center(width)}║{RESET}")
        print(f"{RED}║{' ' * width}║{RESET}")
        print(f"{RED}╚{'═' * width}╝{RESET}\n")
    elif result == RESULT_TIE:
        print(f"\n{YELLOW}╔{'═' * width}╗{RESET}")
        print(f"{YELLOW}║{' ' * width}║{RESET}")
        print(f"{YELLOW}║{'🤝🤝🤝   T I E !   🤝🤝🤝'.center(width)}║{RESET}")
        print(f"{YELLOW}║{' ' * width}║{RESET}")
        print(f"{YELLOW}║{f'Your hand: {player_value}  |  Dealer: {dealer_value}'.center(width)}║{RESET}")
        print(f"{YELLOW}║{' ' * width}║{RESET}")
        print(f"{YELLOW}╚{'═' * width}╝{RESET}\n")


def print_stats(wins: int, losses: int, ties: int, total: int):
    """Print statistics in a nice box"""
    total_played = wins + losses + ties
    win_rate = (wins / total_played * 100) if total_played > 0 else 0
    
    content = [
        f"Rounds Played:  {total_played}",
        "────────────────────",
        f"✅ Wins:         {wins}",
        f"❌ Losses:       {losses}",
        f"🤝 Ties:         {ties}",
        "────────────────────",
        f"📈 Win Rate:     {win_rate:.1f}%"
    ]
    
    print_box("📊 GAME STATISTICS", content, CYAN)


def print_interesting_stats(stats: dict):
    """Print interesting statistics in a nice box"""
    content = [
        f"🔥 Longest Win Streak:  {stats.get('longest_win_streak', 0)}",
        f"📉 Longest Lose Streak: {stats.get('longest_lose_streak', 0)}",
        f"💥 Biggest Bust:        {stats.get('biggest_bust', 0)}",
        f"🎯 Blackjacks:          {stats.get('blackjacks', 0)}",
        f"💀 Dealer Busts:        {stats.get('dealer_busts', 0)}",
        f"📈 Avg Hand Value:      {stats.get('avg_hand_value', 0):.1f}",
        f"👊 Total Hits:          {stats.get('total_hits', 0)}",
        f"🛑 Total Stands:        {stats.get('total_stands', 0)}"
    ]
    
    print_box("📊 INTERESTING STATS", content, CYAN)


def print_round_header(round_num: int, total_rounds: int):
    """Print round header"""
    width = 60
    title = f"🎰 ROUND {round_num} of {total_rounds} 🎰"
    print(f"\n{MAGENTA}╔{'═' * width}╗{RESET}")
    print(f"{MAGENTA}║{title.center(width)}║{RESET}")
    print(f"{MAGENTA}╚{'═' * width}╝{RESET}\n")


def print_hit_stand_prompt():
    """Print hit/stand prompt in a nice box"""
    print(f"\n{CYAN}┌────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  Your move:                        {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}                                    {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}    [H] 👊 HIT  - Draw another card {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}    [S] 🛑 STAND - Keep your hand   {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}                                    {CYAN}│{RESET}")
    print(f"{CYAN}└────────────────────────────────────┘{RESET}\n")


def print_game_state_ascii(my_hand: list, dealer_hand: list = None, dealer_visible_count: int = 1):
    """
    Display current game state with ASCII art cards.
    
    Args:
        my_hand: List of Card objects in player's hand
        dealer_hand: Full list of dealer's cards (optional)
        dealer_visible_count: Number of dealer cards to show (rest hidden)
    """
    width = 60
    
    print(f"\n{MAGENTA}╔{'═' * width}╗{RESET}")
    print(f"{MAGENTA}║{'DEALER\'S HAND'.center(width)}║{RESET}")
    print(f"{MAGENTA}╠{'═' * width}╣{RESET}")
    print(f"{MAGENTA}║{' ' * width}║{RESET}")
    
    # Show dealer's hand
    if dealer_hand is not None and len(dealer_hand) > 0:
        dealer_value = calculate_hand_value(dealer_hand)
        hidden_count = len(dealer_hand) - dealer_visible_count if dealer_visible_count < len(dealer_hand) else 0
        visible_cards = dealer_hand[:dealer_visible_count] if dealer_visible_count <= len(dealer_hand) else dealer_hand
        
        # Print cards inside the box
        print_cards_side_by_side(visible_cards, hidden_count, indent=5)
        # Calculate padding for value line (accounting for ANSI codes)
        value_text = f"{BLUE}Value: {dealer_value}{RESET}"
        # Remove ANSI codes for length calculation
        clean_text = f"Value: {dealer_value}"
        padding = width - len(clean_text) - 4
        print(f"{MAGENTA}║{RESET}  {value_text}{' ' * padding}{MAGENTA}║{RESET}")
    else:
        print(f"{MAGENTA}║{' ' * width}║{RESET}")
    
    print(f"{MAGENTA}║{' ' * width}║{RESET}")
    print(f"{MAGENTA}╠{'═' * width}╣{RESET}")
    print(f"{MAGENTA}║{'YOUR HAND'.center(width)}║{RESET}")
    print(f"{MAGENTA}╠{'═' * width}╣{RESET}")
    print(f"{MAGENTA}║{' ' * width}║{RESET}")
    
    # Show player's hand
    my_value = calculate_hand_value(my_hand)
    print_cards_side_by_side(my_hand, indent=5)
    # Calculate padding for value line (accounting for ANSI codes)
    value_text = f"{GREEN}Value: {my_value}{RESET}"
    # Remove ANSI codes for length calculation
    clean_text = f"Value: {my_value}"
    padding = width - len(clean_text) - 4
    print(f"{MAGENTA}║{RESET}  {value_text}{' ' * padding}{MAGENTA}║{RESET}")
    
    print(f"{MAGENTA}║{' ' * width}║{RESET}")
    print(f"{MAGENTA}╚{'═' * width}╝{RESET}\n")


# ============================================================================
# Network and Game Functions
# ============================================================================

def listen_for_offers() -> tuple:
    """
    Scan for servers and let user choose which one to connect to.
    
    Returns:
        tuple: (server_ip, tcp_port, server_name) or None
    """
    while True:  # Loop allows rescanning
        print(f"\n{CYAN}[🔍] Scanning for servers...{RESET}")
        
        # Dictionary to store found servers: {server_name: (ip, tcp_port)}
        servers = {}
        
        # Create UDP socket
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind(('', UDP_BROADCAST_PORT))
        udp_socket.settimeout(1.0)  # 1 second timeout for each recv
        
        # Scan for 3 seconds
        scan_duration = 3
        start_time = time.time()
        
        while time.time() - start_time < scan_duration:
            try:
                data, server_address = udp_socket.recvfrom(1024)
                parsed = parse_offer_packet(data)
                
                if parsed:
                    tcp_port, server_name = parsed
                    server_ip = server_address[0]
                    
                    # Only print if we haven't seen this server before
                    if server_name not in servers:
                        print(f"  {GREEN}[✅] Found: {server_name}{RESET} at {server_ip}")
                    
                    # Store/update server info
                    servers[server_name] = (server_ip, tcp_port)
                    
            except socket.timeout:
                continue  # Keep scanning
            except Exception as e:
                print(f"  {RED}Error: {e}{RESET}")
        
        udp_socket.close()
        
        # Check if any servers were found
        if not servers:
            print(f"\n{RED}No servers found!{RESET}")
            retry = input(f"{YELLOW}Try again? (y/n): {RESET}").strip().lower()
            if retry == 'y':
                continue
            else:
                return None
        
        # Display server selection menu
        width = 60
        print(f"\n{MAGENTA}╔{'═' * width}╗{RESET}")
        print(f"{MAGENTA}║{'🎰 AVAILABLE CASINOS 🎰'.center(width)}║{RESET}")
        print(f"{MAGENTA}╠{'═' * width}╣{RESET}")
        print(f"{MAGENTA}║{' ' * width}║{RESET}")
        
        server_list = list(servers.items())  # [(name, (ip, port)), ...]
        
        for i, (name, (ip, port)) in enumerate(server_list, start=1):
            emoji = "🏠" if i == 1 else "🎲" if i == 2 else "🃏"
            line = f"  [{i}] {emoji} {name:<25} {ip}:{port}"
            print(f"{MAGENTA}║{RESET}{line:<{width-2}}{MAGENTA}║{RESET}")
        
        print(f"{MAGENTA}║{' ' * width}║{RESET}")
        print(f"{MAGENTA}║{RESET}  [0] 🔄 Rescan for servers{' ' * (width - 28)}{MAGENTA}║{RESET}")
        print(f"{MAGENTA}║{' ' * width}║{RESET}")
        print(f"{MAGENTA}╚{'═' * width}╝{RESET}")
        
        # Get user choice
        try:
            choice = int(input(f"\n{CYAN}Enter your choice: {RESET}").strip())
            
            if choice == 0:
                continue  # Rescan
            
            if choice < 1 or choice > len(server_list):
                print(f"{RED}Invalid choice!{RESET}")
                continue
            
            # Get selected server
            selected_name, (selected_ip, selected_port) = server_list[choice - 1]
            print(f"\n{GREEN}[✅] Selected: {selected_name}{RESET}")
            
            return (selected_ip, selected_port, selected_name)
        
        except ValueError:
            print(f"{RED}Please enter a number!{RESET}")
            continue
        except (EOFError, KeyboardInterrupt):
            return None


def receive_card(tcp_socket: socket.socket) -> tuple:
    """
    Helper: receive card from server, return (result, Card).
    
    Args:
        tcp_socket: The TCP socket connected to server
    
    Returns:
        tuple: (result, Card) where result is RESULT_* constant and Card is the card object
    
    Raises:
        Exception: If packet is invalid or connection lost
    """
    try:
        # Receive exactly 9 bytes (size of server payload packet)
        # TCP is a stream protocol, so we need to keep receiving until we have all bytes
        data = b''
        while len(data) < 9:
            chunk = tcp_socket.recv(9 - len(data))
            if len(chunk) == 0:
                raise Exception("Connection closed by server")
            data += chunk
        
        parsed = parse_payload_server(data)
        if parsed is None:
            raise Exception("Invalid payload packet from server")
        
        result, card_rank, card_suit = parsed
        card = Card(card_rank, card_suit)
        
        return (result, card)
    
    except socket.timeout:
        raise Exception("Timeout waiting for card from server")
    except Exception as e:
        raise Exception(f"Error receiving card: {e}")


def send_decision(tcp_socket: socket.socket, decision: str):
    """
    Helper: send Hit or Stand decision.
    
    Args:
        tcp_socket: The TCP socket connected to server
        decision: Either "Hittt" or "Stand"
    """
    try:
        packet = create_payload_client(decision)
        tcp_socket.sendall(packet)
    except Exception as e:
        print(f"\033[91m[ERROR] Failed to send decision: {e}\033[0m")
        raise


def get_user_decision() -> str:
    """
    Ask user for hit/stand, return 'Hittt' or 'Stand'.
    
    Returns:
        str: "Hittt" or "Stand"
    """
    while True:
        try:
            print_hit_stand_prompt()
            choice = input(f"{CYAN}Choice (h/s): {RESET}").strip().lower()
            if choice == 'h' or choice == 'hit':
                return "Hittt"
            elif choice == 's' or choice == 'stand':
                return "Stand"
            else:
                print(f"{YELLOW}Please enter 'h' for Hit or 's' for Stand{RESET}")
        except (EOFError, KeyboardInterrupt):
            # User pressed Ctrl+C or EOF
            print(f"\n{YELLOW}Standing...{RESET}")
            return "Stand"


def print_game_state(my_hand: list, dealer_card: Card = None, dealer_hand: list = None):
    """
    Display current game state nicely.
    
    Args:
        my_hand: List of Card objects in player's hand
        dealer_card: Single Card that dealer is showing (optional)
        dealer_hand: Full list of dealer's cards (optional, for end of round)
    """
    print("\n" + "="*60)
    print("\033[95mCurrent Game State:\033[0m")
    print("="*60)
    
    # Show player's hand
    my_value = calculate_hand_value(my_hand)
    print(f"\033[92mYour hand: {format_hand(my_hand)}\033[0m")
    
    # Show dealer's hand
    if dealer_hand is not None:
        # Show full dealer hand (end of round)
        dealer_value = calculate_hand_value(dealer_hand)
        print(f"\033[91mDealer hand: {format_hand(dealer_hand)}\033[0m")
    elif dealer_card is not None:
        # Show only visible dealer card (during play)
        print(f"\033[91mDealer shows: {dealer_card}\033[0m")
    else:
        print(f"\033[91mDealer: (no card shown yet)\033[0m")
    
    print("="*60 + "\n")


def play_round(tcp_socket: socket.socket, round_num: int, total_rounds: int = 1, game_stats: dict = None) -> tuple:
    """
    Play one round, return result (RESULT_WIN/RESULT_LOSS/RESULT_TIE).
    
    Args:
        tcp_socket: The TCP socket connected to server
        round_num: Round number for display
        total_rounds: Total number of rounds
    
    Returns:
        int: Result constant (RESULT_WIN, RESULT_LOSS, or RESULT_TIE)
    """
    print_round_header(round_num, total_rounds)
    
    my_hand = []
    dealer_hand = []
    dealer_visible_card = None
    
    # Receive 2 cards from server (my hand)
    print(f"{CYAN}[📥] Receiving your cards...{RESET}")
    for i in range(2):
        result, card = receive_card(tcp_socket)
        my_hand.append(card)
        time.sleep(0.3)  # Dramatic effect
        print(f"  {GREEN}✓{RESET} Received: {card}")
    
    # Receive 1 card (dealer's visible card)
    print(f"\n{CYAN}[📥] Receiving dealer's card...{RESET}")
    result, dealer_visible_card = receive_card(tcp_socket)
    dealer_hand.append(dealer_visible_card)
    time.sleep(0.3)
    print(f"  {BLUE}✓{RESET} Dealer shows: {dealer_visible_card}")
    
    # Display initial state with ASCII art
    print_game_state_ascii(my_hand, dealer_hand, dealer_visible_count=1)
    
    # PLAYER TURN
    print(f"{CYAN}[YOUR TURN]{RESET}")
    player_bust = False
    hits_this_round = 0
    stands_this_round = 0
    
    # Check for blackjack (21 with 2 cards)
    if len(my_hand) == 2 and calculate_hand_value(my_hand) == 21:
        if game_stats is not None:
            game_stats['blackjacks'] = game_stats.get('blackjacks', 0) + 1
    
    while True:
        # Check if already bust (shouldn't happen, but just in case)
        if is_bust(my_hand):
            my_value = calculate_hand_value(my_hand)
            player_bust = True
            # Track biggest bust
            if game_stats is not None:
                game_stats['biggest_bust'] = max(game_stats.get('biggest_bust', 0), my_value)
            print_result_screen(RESULT_LOSS, my_value, 0, player_bust=True)
            return (RESULT_LOSS, hits_this_round, stands_this_round, my_value)
        
        # Get user decision
        decision = get_user_decision()
        
        # Send decision to server
        send_decision(tcp_socket, decision)
        
        if decision == "Hittt":
            hits_this_round += 1
            # Receive new card
            result, card = receive_card(tcp_socket)
            my_hand.append(card)
            time.sleep(0.3)
            print(f"\n{GREEN}[✓] You received: {card}{RESET}")
            
            # Update display
            print_game_state_ascii(my_hand, dealer_hand, dealer_visible_count=1)
            
            # Check if round ended (I busted)
            if result != RESULT_NOT_OVER:
                my_value = calculate_hand_value(my_hand)
                player_bust = True
                # Track biggest bust
                if game_stats is not None:
                    game_stats['biggest_bust'] = max(game_stats.get('biggest_bust', 0), my_value)
                print_result_screen(RESULT_LOSS, my_value, 0, player_bust=True)
                if result == RESULT_LOSS:
                    return (RESULT_LOSS, hits_this_round, stands_this_round, my_value)
                return (result, hits_this_round, stands_this_round, my_value)
        
        elif decision == "Stand":
            stands_this_round += 1
            my_value = calculate_hand_value(my_hand)
            print(f"\n{YELLOW}You stand with {my_value}{RESET}")
            break
    
    # WAIT FOR DEALER
    print(f"\n{CYAN}[DEALER'S TURN]{RESET}")
    print(f"{BLUE}Waiting for dealer to play...{RESET}\n")
    
    # Receive dealer's cards until result != NOT_OVER
    while True:
        result, card = receive_card(tcp_socket)
        
        # Only add card if round is still in progress (not a dummy card)
        if result == RESULT_NOT_OVER:
            # Check if this is the first dealer card we're receiving (the hidden one)
            if len(dealer_hand) == 1:
                print(f"{BLUE}[🃏] Dealer reveals: {card}{RESET}")
            else:
                print(f"{BLUE}[🃏] Dealer draws: {card}{RESET}")
            dealer_hand.append(card)
            time.sleep(0.5)  # Dramatic effect
            # Update display
            print_game_state_ascii(my_hand, dealer_hand, dealer_visible_count=len(dealer_hand))
        else:
            # Result received, this is a dummy card - don't add it to dealer_hand
            break
    
    # SHOW RESULT
    my_value = calculate_hand_value(my_hand)
    dealer_value = calculate_hand_value(dealer_hand)
    dealer_bust = dealer_value > 21
    
    # Track dealer busts
    if dealer_bust and game_stats is not None:
        game_stats['dealer_busts'] = game_stats.get('dealer_busts', 0) + 1
    
    # Track average hand value
    if game_stats is not None:
        if 'hand_values' not in game_stats:
            game_stats['hand_values'] = []
        game_stats['hand_values'].append(my_value)
    
    # Final display
    print_game_state_ascii(my_hand, dealer_hand, dealer_visible_count=len(dealer_hand))
    
    # Show result screen
    if dealer_bust:
        print_result_screen(RESULT_WIN, my_value, dealer_value, dealer_bust=True)
        return (RESULT_WIN, hits_this_round, stands_this_round, my_value)
    else:
        print_result_screen(result, my_value, dealer_value)
        return (result, hits_this_round, stands_this_round, my_value)


def play_game(server_ip: str, tcp_port: int, num_rounds: int) -> dict:
    """
    Connect to server and play all rounds, return statistics dict.
    
    Args:
        server_ip: IP address of the server
        tcp_port: TCP port number of the server
        num_rounds: Number of rounds to play
    
    Returns:
        dict: Statistics with keys 'wins', 'losses', 'ties', 'total'
    """
    tcp_socket = None
    try:
        # Create TCP socket and connect
        print(f"\n{CYAN}[🔌] Connecting to server...{RESET}")
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(30.0)  # 30 second timeout
        tcp_socket.connect((server_ip, tcp_port))
        print(f"{GREEN}[✅] Connected successfully!{RESET}")
        
        # Send request packet
        request_packet = create_request_packet(num_rounds, TEAM_NAME)
        tcp_socket.sendall(request_packet)
        print(f"{CYAN}[📤] Requesting {num_rounds} rounds...{RESET}")
        print(f"{GREEN}[🎮] Game starting!{RESET}\n")
        
        # Initialize statistics
        stats = {
            'wins': 0, 
            'losses': 0, 
            'ties': 0, 
            'total': num_rounds,
            'longest_win_streak': 0,
            'longest_lose_streak': 0,
            'current_streak': 0,
            'current_streak_type': None,  # 'win' or 'loss'
            'biggest_bust': 0,
            'blackjacks': 0,
            'dealer_busts': 0,
            'hand_values': [],
            'total_hits': 0,
            'total_stands': 0
        }
        
        # Play all rounds
        for round_num in range(1, num_rounds + 1):
            try:
                result, hits, stands, hand_value = play_round(tcp_socket, round_num, num_rounds, stats)
                
                # Update basic stats
                if result == RESULT_WIN:
                    stats['wins'] += 1
                    # Update streaks
                    if stats['current_streak_type'] == 'win':
                        stats['current_streak'] += 1
                    else:
                        stats['current_streak'] = 1
                        stats['current_streak_type'] = 'win'
                    stats['longest_win_streak'] = max(stats['longest_win_streak'], stats['current_streak'])
                elif result == RESULT_LOSS:
                    stats['losses'] += 1
                    # Update streaks
                    if stats['current_streak_type'] == 'loss':
                        stats['current_streak'] += 1
                    else:
                        stats['current_streak'] = 1
                        stats['current_streak_type'] = 'loss'
                    stats['longest_lose_streak'] = max(stats['longest_lose_streak'], stats['current_streak'])
                elif result == RESULT_TIE:
                    stats['ties'] += 1
                    # Reset streak on tie
                    stats['current_streak'] = 0
                    stats['current_streak_type'] = None
                
                # Update action stats
                stats['total_hits'] += hits
                stats['total_stands'] += stands
                
            except Exception as e:
                print(f"{RED}[❌] Round {round_num} failed: {e}{RESET}")
                break
        
        # Calculate average hand value
        if stats['hand_values']:
            stats['avg_hand_value'] = sum(stats['hand_values']) / len(stats['hand_values'])
        else:
            stats['avg_hand_value'] = 0
        
        # Print summary using print_stats
        total_played = stats['wins'] + stats['losses'] + stats['ties']
        print_stats(stats['wins'], stats['losses'], stats['ties'], num_rounds)
        
        # Print interesting stats
        print_interesting_stats(stats)
        
        return stats
    
    except socket.timeout:
        print(f"{RED}[❌] Connection timeout{RESET}")
        return {'wins': 0, 'losses': 0, 'ties': 0, 'total': 0}
    except Exception as e:
        print(f"{RED}[❌] Connection error: {e}{RESET}")
        return {'wins': 0, 'losses': 0, 'ties': 0, 'total': 0}
    finally:
        if tcp_socket:
            try:
                tcp_socket.close()
                print(f"{CYAN}[🔌] Connection closed{RESET}")
            except:
                pass


def main():
    """Main client entry point."""
    # Print welcome screen
    print_welcome()
    
    print(f"{CYAN}Client started, listening for offer requests...{RESET}")
    
    try:
        while True:
            # Ask user how many rounds
            try:
                num_rounds_input = input(f"\n{CYAN}How many rounds do you want to play? {RESET}").strip()
                num_rounds = int(num_rounds_input)
                if num_rounds < 1 or num_rounds > 255:
                    print(f"{YELLOW}Please enter a number between 1 and 255{RESET}")
                    continue
            except ValueError:
                print(f"{YELLOW}Please enter a valid number{RESET}")
                continue
            except (EOFError, KeyboardInterrupt):
                print(f"\n{YELLOW}Exiting...{RESET}")
                break
            
            # Listen for offers
            try:
                server_ip, tcp_port, server_name = listen_for_offers()
                if server_ip is None:
                    continue  # User cancelled or no servers found
            except KeyboardInterrupt:
                print(f"\n{YELLOW}Exiting...{RESET}")
                break
            
            # Play the game
            stats = play_game(server_ip, tcp_port, num_rounds)
            
            # Calculate and print final win rate
            total_played = stats['wins'] + stats['losses'] + stats['ties']
            if total_played > 0:
                win_rate = (stats['wins'] / total_played) * 100
                print(f"\n{GREEN}Finished playing {total_played} rounds, win rate: {win_rate:.1f}%{RESET}")
            
            # Ask if user wants to play again
            try:
                play_again = input(f"\n{CYAN}Play again? (y/n): {RESET}").strip().lower()
                if play_again != 'y' and play_again != 'yes':
                    print(f"\n{MAGENTA}╔{'═' * 60}╗{RESET}")
                    print(f"{MAGENTA}║{'Thanks for playing! Goodbye! 👋'.center(60)}║{RESET}")
                    print(f"{MAGENTA}╚{'═' * 60}╝{RESET}\n")
                    break
            except (EOFError, KeyboardInterrupt):
                print(f"\n{YELLOW}Thanks for playing! Goodbye!{RESET}")
                break
    
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Exiting...{RESET}")
    except Exception as e:
        print(f"{RED}[FATAL ERROR] {e}{RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

