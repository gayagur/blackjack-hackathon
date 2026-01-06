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
    RESULT_WIN
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
    is_bust
)
from display import (
    print_welcome,
    print_server_menu,
    print_round_header,
    print_game_state,
    print_decision_prompt,
    print_result,
    print_bust,
    print_stats,
    print_interesting_stats,
    print_message,
    print_goodbye,
    RED,
    GREEN,
    YELLOW,
    BLUE,
    MAGENTA,
    CYAN,
    RESET
)


# ============================================================================
# Network and Game Functions
# ============================================================================


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
        print_message("Scanning for servers...", "search")
        
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
                        print_message(f"Found: {server_name} at {server_ip}", "success")
                    
                    # Store/update server info
                    servers[server_name] = (server_ip, tcp_port)
                    
            except socket.timeout:
                continue  # Keep scanning
            except Exception as e:
                print(f"  {RED}Error: {e}{RESET}")
        
        udp_socket.close()
        
        # Check if any servers were found
        if not servers:
            print_message("No servers found!", "error")
            retry = input(f"{YELLOW}Try again? (y/n): {RESET}").strip().lower()
            if retry == 'y':
                continue
            else:
                return None
        
        # Display server selection menu
        print_server_menu(servers)
        server_list = list(servers.items())  # [(name, (ip, port)), ...]
        
        # Get user choice
        try:
            choice = int(input(f"\n{CYAN}Enter your choice: {RESET}").strip())
            
            if choice == 0:
                continue  # Rescan
            
            if choice < 1 or choice > len(server_list):
                print_message("Invalid choice!", "error")
                continue
            
            # Get selected server
            selected_name, (selected_ip, selected_port) = server_list[choice - 1]
            print_message(f"Selected: {selected_name}", "success")
            
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
            print_decision_prompt()
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
    print_message("Receiving your cards...", "receive")
    for i in range(2):
        result, card = receive_card(tcp_socket)
        my_hand.append(card)
        time.sleep(0.3)  # Dramatic effect
        print_message(f"Received: {card}", "success")
    
    # Receive 1 card (dealer's visible card)
    print_message("Receiving dealer's card...", "receive")
    result, dealer_visible_card = receive_card(tcp_socket)
    dealer_hand.append(dealer_visible_card)
    # Add a placeholder for the hidden card so we can display it as hidden
    # We'll use None as a placeholder - print_cards_row will handle it
    dealer_hand.append(None)  # Placeholder for hidden card
    time.sleep(0.3)
    print_message(f"Dealer shows: {dealer_visible_card}", "info")
    
    # Display initial state with ASCII art - hide second dealer card
    print_game_state(my_hand, dealer_hand, hide_dealer_card=True)
    
    # PLAYER TURN
    print_message("YOUR TURN", "game")
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
            print_bust(my_value, is_player=True)
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
            print_message(f"You received: {card}", "success")
            
            # Update display - still hide dealer's second card
            print_game_state(my_hand, dealer_hand, hide_dealer_card=True)
            
            # Check if round ended (I busted)
            if result != RESULT_NOT_OVER:
                my_value = calculate_hand_value(my_hand)
                player_bust = True
                # Track biggest bust
                if game_stats is not None:
                    game_stats['biggest_bust'] = max(game_stats.get('biggest_bust', 0), my_value)
                print_bust(my_value, is_player=True)
                if result == RESULT_LOSS:
                    return (RESULT_LOSS, hits_this_round, stands_this_round, my_value)
                return (result, hits_this_round, stands_this_round, my_value)
        
        elif decision == "Stand":
            stands_this_round += 1
            my_value = calculate_hand_value(my_hand)
            print_message(f"You stand with {my_value}", "info")
            break
    
    # WAIT FOR DEALER
    print_message("DEALER'S TURN", "game")
    print_message("Waiting for dealer to play...", "info")
    
    # Receive dealer's cards until result != NOT_OVER
    while True:
        result, card = receive_card(tcp_socket)
        
        # Only add card if round is still in progress (not a dummy card)
        if result == RESULT_NOT_OVER:
            # Check if this is the hidden card we're receiving (replacing the None placeholder)
            if len(dealer_hand) == 2 and dealer_hand[1] is None:
                # Replace the None placeholder with the actual hidden card
                dealer_hand[1] = card
                print_message(f"Dealer reveals: {card}", "info")
            else:
                # Additional cards after reveal
                dealer_hand.append(card)
                print_message(f"Dealer draws: {card}", "info")
            time.sleep(0.5)  # Dramatic effect
            # Update display - show all cards now (no more hiding)
            print_game_state(my_hand, dealer_hand, hide_dealer_card=False)
        else:
            # Result received, this is a dummy card - don't add it to dealer_hand
            break
    
    # SHOW RESULT
    my_value = calculate_hand_value(my_hand)
    # Filter out None placeholders before calculating dealer value
    visible_dealer_cards = [c for c in dealer_hand if c is not None]
    dealer_value = calculate_hand_value(visible_dealer_cards)
    dealer_bust = dealer_value > 21
    
    # Track dealer busts
    if dealer_bust and game_stats is not None:
        game_stats['dealer_busts'] = game_stats.get('dealer_busts', 0) + 1
    
    # Track average hand value
    if game_stats is not None:
        if 'hand_values' not in game_stats:
            game_stats['hand_values'] = []
        game_stats['hand_values'].append(my_value)
    
    # Final display - show all cards
    print_game_state(my_hand, dealer_hand, hide_dealer_card=False)
    
    # Show result screen
    if dealer_bust:
        print_bust(dealer_value, is_player=False)
        print_result(RESULT_WIN, my_value, dealer_value)
        return (RESULT_WIN, hits_this_round, stands_this_round, my_value)
    else:
        print_result(result, my_value, dealer_value)
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
        print_message("Connecting to server...", "connect")
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(30.0)  # 30 second timeout
        tcp_socket.connect((server_ip, tcp_port))
        print_message("Connected successfully!", "success")
        
        # Send request packet
        request_packet = create_request_packet(num_rounds, TEAM_NAME)
        tcp_socket.sendall(request_packet)
        print_message(f"Requesting {num_rounds} rounds...", "send")
        print_message("Game starting!", "game")
        
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
                print_message(f"Round {round_num} failed: {e}", "error")
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
        print_message("Connection timeout", "error")
        return {'wins': 0, 'losses': 0, 'ties': 0, 'total': 0}
    except Exception as e:
        print_message(f"Connection error: {e}", "error")
        return {'wins': 0, 'losses': 0, 'ties': 0, 'total': 0}
    finally:
        if tcp_socket:
            try:
                tcp_socket.close()
                print_message("Connection closed", "connect")
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
                    print_goodbye()
                    break
            except (EOFError, KeyboardInterrupt):
                print_goodbye()
                break
    
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Exiting...{RESET}")
    except Exception as e:
        print_message(f"FATAL ERROR: {e}", "error")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

