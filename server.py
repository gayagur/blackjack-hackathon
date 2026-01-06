"""
Server module for Blackjack Client-Server Game

This module implements the Blackjack dealer/server that:
- Broadcasts UDP offers to discover clients
- Accepts TCP connections from clients
- Plays rounds of Blackjack with each client
"""

import socket
import threading
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
    create_offer_packet,
    parse_request_packet,
    create_payload_server,
    parse_payload_client
)
from game_logic import (
    Deck,
    Card,
    calculate_hand_value,
    is_bust,
    format_hand
)


def get_local_ip() -> str:
    """
    Get the local IP address of this machine.
    
    Returns:
        str: Local IP address as a string
    """
    # Connect to a remote address to determine local IP
    # (doesn't actually send data, just determines route)
    try:
        # Use a non-routable address to avoid actual connection
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google DNS
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback: try to get hostname IP
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"  # Ultimate fallback


def broadcast_offers(tcp_port: int, stop_event: threading.Event):
    """
    Background thread: broadcast UDP offers every second.
    
    Args:
        tcp_port: The TCP port number to include in offers
        stop_event: Threading event to signal when to stop broadcasting
    """
    try:
        # Create UDP socket with broadcast option
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Create offer packet
        offer_packet = create_offer_packet(tcp_port, TEAM_NAME)
        broadcast_addr = ('<broadcast>', UDP_BROADCAST_PORT)
        
        print(f"\033[92m[UDP] Broadcasting offers on port {UDP_BROADCAST_PORT}...\033[0m")
        
        # Broadcast every second until stop event is set
        while not stop_event.is_set():
            try:
                udp_socket.sendto(offer_packet, broadcast_addr)
                print(f"\033[92m[UDP] Sent offer packet (TCP port: {tcp_port})\033[0m")
            except Exception as e:
                print(f"\033[91m[UDP] Error broadcasting: {e}\033[0m")
            
            # Wait 1 second, but check stop_event periodically
            stop_event.wait(timeout=1.0)
        
        udp_socket.close()
        print("\033[92m[UDP] Broadcast thread stopped\033[0m")
    
    except Exception as e:
        print(f"\033[91m[UDP] Fatal error in broadcast thread: {e}\033[0m")


def send_card(client_socket: socket.socket, card: Card, result: int):
    """
    Helper: send a card to the client via payload packet.
    
    Args:
        client_socket: The client's TCP socket
        card: The Card object to send
        result: Game result (RESULT_NOT_OVER, RESULT_WIN, RESULT_LOSS, RESULT_TIE)
    """
    try:
        packet = create_payload_server(result, card.rank, card.suit)
        client_socket.sendall(packet)
    except Exception as e:
        print(f"\033[91m[ERROR] Failed to send card: {e}\033[0m")
        raise


def receive_decision(client_socket: socket.socket) -> str:
    """
    Helper: receive and parse player decision.
    
    Args:
        client_socket: The client's TCP socket
    
    Returns:
        str: Player decision ("Hittt" or "Stand")
    
    Raises:
        Exception: If packet is invalid or connection lost
    """
    try:
        # Receive exactly 10 bytes (size of client payload packet)
        # TCP is a stream protocol, so we need to keep receiving until we have all bytes
        data = b''
        while len(data) < 10:
            chunk = client_socket.recv(10 - len(data))
            if len(chunk) == 0:
                raise Exception("Connection closed by client")
            data += chunk
        
        decision = parse_payload_client(data)
        if decision is None:
            raise Exception("Invalid payload packet from client")
        
        return decision
    
    except socket.timeout:
        raise Exception("Timeout waiting for player decision")
    except Exception as e:
        raise Exception(f"Error receiving decision: {e}")


def play_round(client_socket: socket.socket, client_name: str, round_num: int) -> int:
    """
    Play one round of blackjack, return result (RESULT_WIN/RESULT_LOSS/RESULT_TIE).
    
    Args:
        client_socket: The client's TCP socket
        client_name: Name of the client for printing
        round_num: Round number for display
    
    Returns:
        int: Result constant (RESULT_WIN, RESULT_LOSS, or RESULT_TIE)
    """
    print(f"\n\033[95m{'='*60}\033[0m")
    print(f"\033[95mRound {round_num} - {client_name}\033[0m")
    print(f"\033[95m{'='*60}\033[0m")
    
    # Create a new shuffled deck
    deck = Deck()
    player_hand = []
    dealer_hand = []
    
    # Deal 2 cards to player
    print(f"\033[94m[DEAL] Dealing cards to player...\033[0m")
    for i in range(2):
        card = deck.draw()
        player_hand.append(card)
        send_card(client_socket, card, RESULT_NOT_OVER)
        print(f"  Player receives: {card}")
    
    # Deal 2 cards to dealer (keep second hidden)
    print(f"\033[94m[DEAL] Dealing cards to dealer...\033[0m")
    for i in range(2):
        card = deck.draw()
        dealer_hand.append(card)
        if i == 0:
            # Send first card to player
            send_card(client_socket, card, RESULT_NOT_OVER)
            print(f"  Dealer shows: {card}")
        else:
            print(f"  Dealer's hidden card: {card}")
    
    print(f"\n\033[93mPlayer hand: {format_hand(player_hand)}\033[0m")
    print(f"\033[93mDealer shows: {format_hand([dealer_hand[0]])}\033[0m")
    
    # PLAYER TURN
    print(f"\n\033[96m[PLAYER TURN]\033[0m")
    while True:
        try:
            decision = receive_decision(client_socket)
            print(f"  Player decision: {decision}")
            
            if decision == "Hittt":
                # Draw card for player
                card = deck.draw()
                player_hand.append(card)
                print(f"  Player receives: {card}")
                print(f"  Player hand: {format_hand(player_hand)}")
                
                # Send card to player
                send_card(client_socket, card, RESULT_NOT_OVER)
                
                # Check if player busts
                if is_bust(player_hand):
                    print(f"\033[91m  Player BUSTS! ({calculate_hand_value(player_hand)})\033[0m")
                    send_card(client_socket, Card(1, 0), RESULT_LOSS)  # Dummy card with result
                    return RESULT_LOSS
            
            elif decision == "Stand":
                print(f"  Player stands with {calculate_hand_value(player_hand)}")
                break
            
        except Exception as e:
            print(f"\033[91m[ERROR] {e}\033[0m")
            return RESULT_LOSS
    
    # DEALER TURN (only if player didn't bust)
    player_value = calculate_hand_value(player_hand)
    print(f"\n\033[96m[DEALER TURN]\033[0m")
    
    # Reveal dealer's hidden card
    hidden_card = dealer_hand[1]
    send_card(client_socket, hidden_card, RESULT_NOT_OVER)
    print(f"  Dealer reveals: {hidden_card}")
    print(f"  Dealer hand: {format_hand(dealer_hand)}")
    
    # Check if dealer already busted with initial 2 cards (e.g., two Aces = 22)
    if is_bust(dealer_hand):
        dealer_value = calculate_hand_value(dealer_hand)
        print(f"\033[91m  Dealer BUSTS! ({dealer_value})\033[0m")
        send_card(client_socket, Card(1, 0), RESULT_WIN)  # Dummy card with result
        return RESULT_WIN
    
    # Dealer must hit until 17 or higher
    while calculate_hand_value(dealer_hand) < 17:
        card = deck.draw()
        dealer_hand.append(card)
        print(f"  Dealer draws: {card}")
        print(f"  Dealer hand: {format_hand(dealer_hand)}")
        
        # Send card to player
        send_card(client_socket, card, RESULT_NOT_OVER)
        
        # CRITICAL: Check if dealer busts AFTER each card
        dealer_value = calculate_hand_value(dealer_hand)
        if dealer_value > 21:  # Explicit check for bust
            print(f"\033[91m  Dealer BUSTS! ({dealer_value})\033[0m")
            send_card(client_socket, Card(1, 0), RESULT_WIN)  # Dummy card with result
            return RESULT_WIN  # Player wins immediately - MUST return here!
    
    # After loop ends, dealer has >= 17, but MUST check for bust before comparing
    dealer_value = calculate_hand_value(dealer_hand)
    
    # CRITICAL: Check bust before any comparison - dealer might have 22+ even if >= 17
    if dealer_value > 21:
        print(f"\033[91m  Dealer BUSTS! ({dealer_value})\033[0m")
        send_card(client_socket, Card(1, 0), RESULT_WIN)  # Dummy card with result
        return RESULT_WIN  # Player wins - MUST return, don't continue to comparison!
    
    # Only reach here if dealer didn't bust (value is 17-21)
    print(f"  Dealer stands with {dealer_value}")
    
    # DETERMINE WINNER
    # NOTE: We only reach here if dealer did NOT bust (dealer_value <= 21)
    # If dealer busted, we would have returned RESULT_WIN already above
    print(f"\n\033[96m[RESULT]\033[0m")
    print(f"  Player: {format_hand(player_hand)}")
    print(f"  Dealer: {format_hand(dealer_hand)}")
    
    # Recalculate values to ensure accuracy
    player_value = calculate_hand_value(player_hand)
    dealer_value = calculate_hand_value(dealer_hand)
    
    # Safety check: if dealer somehow busted, player wins (shouldn't reach here)
    if dealer_value > 21:
        print(f"\033[91m  Dealer BUSTS! ({dealer_value}) - Player WINS!\033[0m")
        send_card(client_socket, Card(1, 0), RESULT_WIN)
        return RESULT_WIN
    
    if player_value > dealer_value:
        result = RESULT_WIN
        print(f"\033[92m  Player WINS! ({player_value} > {dealer_value})\033[0m")
    elif dealer_value > player_value:
        result = RESULT_LOSS
        print(f"\033[91m  Player LOSES! ({dealer_value} > {player_value})\033[0m")
    else:
        result = RESULT_TIE
        print(f"\033[93m  TIE! ({player_value} = {dealer_value})\033[0m")
    
    # Send final result (use dummy card)
    send_card(client_socket, Card(1, 0), result)
    
    return result


def handle_client(client_socket: socket.socket, client_address: tuple):
    """
    Handle a single client connection - play all requested rounds.
    
    Args:
        client_socket: The client's TCP socket
        client_address: Tuple of (ip, port) of the client
    """
    client_name = "Unknown"
    try:
        # Set socket timeout for robustness
        client_socket.settimeout(30.0)  # 30 second timeout
        
        print(f"\n\033[92m[CONNECTION] Client connected from {client_address}\033[0m")
        
        # Receive and parse the request packet (38 bytes)
        # TCP is a stream protocol, so we need to keep receiving until we have all bytes
        data = b''
        while len(data) < 38:
            chunk = client_socket.recv(38 - len(data))
            if len(chunk) == 0:
                print(f"\033[91m[ERROR] Connection closed by client before sending request\033[0m")
                client_socket.close()
                return
            data += chunk
        
        parsed = parse_request_packet(data)
        if parsed is None:
            print(f"\033[91m[ERROR] Invalid request packet from {client_address}\033[0m")
            client_socket.close()
            return
        
        num_rounds, client_name = parsed
        print(f"\033[92mClient {client_name} connected, wants to play {num_rounds} rounds\033[0m")
        
        # Play all requested rounds
        wins = 0
        losses = 0
        ties = 0
        
        for round_num in range(1, num_rounds + 1):
            try:
                result = play_round(client_socket, client_name, round_num)
                if result == RESULT_WIN:
                    wins += 1
                elif result == RESULT_LOSS:
                    losses += 1
                else:
                    ties += 1
            except Exception as e:
                print(f"\033[91m[ERROR] Round {round_num} failed: {e}\033[0m")
                break
        
        # Print summary
        print(f"\n\033[95m{'='*60}\033[0m")
        print(f"\033[95mGame Summary for {client_name}:\033[0m")
        print(f"  Wins: {wins}")
        print(f"  Losses: {losses}")
        print(f"  Ties: {ties}")
        print(f"\033[95m{'='*60}\033[0m\n")
        
    except socket.timeout:
        print(f"\033[91m[ERROR] Timeout waiting for client {client_name}\033[0m")
    except Exception as e:
        print(f"\033[91m[ERROR] Error handling client {client_name}: {e}\033[0m")
    finally:
        try:
            client_socket.close()
            print(f"\033[92m[CONNECTION] Closed connection with {client_name}\033[0m")
        except:
            pass


def main():
    """Main server entry point."""
    try:
        # Create TCP socket and bind to port 0 (OS chooses available port)
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_socket.bind(('', 0))  # Bind to all interfaces, port 0
        
        # Get the assigned port number
        tcp_port = tcp_socket.getsockname()[1]
        
        # Get local IP address
        local_ip = get_local_ip()
        
        # Start listening
        tcp_socket.listen(5)
        
        print(f"\n\033[95m{'='*60}\033[0m")
        print(f"\033[95mBlackjack Server Started\033[0m")
        print(f"\033[95m{'='*60}\033[0m")
        print(f"Server started, listening on IP address {local_ip}")
        print(f"TCP port: {tcp_port}")
        print(f"Team name: {TEAM_NAME}")
        print(f"\033[95m{'='*60}\033[0m\n")
        
        # Start UDP broadcast thread
        stop_event = threading.Event()
        broadcast_thread = threading.Thread(
            target=broadcast_offers,
            args=(tcp_port, stop_event),
            daemon=True
        )
        broadcast_thread.start()
        
        # Main loop: accept connections
        print(f"\033[92m[TCP] Waiting for client connections...\033[0m")
        try:
            while True:
                client_socket, client_address = tcp_socket.accept()
                
                # Spawn a new thread to handle this client
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
        
        except KeyboardInterrupt:
            print(f"\n\033[93m[SHUTDOWN] Server shutting down...\033[0m")
            stop_event.set()
            tcp_socket.close()
            print(f"\033[93m[SHUTDOWN] Server stopped\033[0m")
    
    except Exception as e:
        print(f"\033[91m[FATAL ERROR] {e}\033[0m")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

