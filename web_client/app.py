"""
Flask Web Server - Professional Blackjack Web Client
Bridge between Web Client and Python Blackjack Server
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import socket
import threading
import time
from protocol import (
    parse_offer_packet,
    create_request_packet,
    parse_payload_server,
    create_payload_client
)
from game_logic import Card, calculate_hand_value, is_bust
from constants import (
    UDP_BROADCAST_PORT, 
    TEAM_NAME, 
    RESULT_NOT_OVER,
    RESULT_WIN,
    RESULT_LOSS,
    RESULT_TIE,
    MODE_CLASSIC,
    MODE_CASINO,
    MODE_BOT,
    STARTING_CHIPS,
    MIN_BET,
    MAX_BET,
    BLACKJACK_MULTIPLIER,
    DOUBLE_DOWN_ENABLED
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blackjack-professional-2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Store active game connections
active_games = {}


# ============================================================================
# Statistics System
# ============================================================================

class GameStatistics:
    """Track all game statistics across all modes"""
    
    def __init__(self):
        # === BASIC STATS (All Modes) ===
        self.rounds_played = 0
        self.wins = 0
        self.losses = 0
        self.ties = 0
        
        # === STREAK STATS (All Modes) ===
        self.current_streak = 0
        self.longest_win_streak = 0
        self.longest_lose_streak = 0
        
        # === HAND STATS (All Modes) ===
        self.total_hand_value = 0
        self.blackjacks = 0
        self.busts = 0
        self.biggest_bust = 0
        self.perfect_21s = 0
        
        # === DECISION STATS (All Modes) ===
        self.total_hits = 0
        self.total_stands = 0
        self.hits_that_busted = 0
        
        # === DEALER STATS (All Modes) ===
        self.dealer_busts = 0
        self.dealer_blackjacks = 0
        self.times_beat_dealer = 0
        self.times_lost_to_dealer = 0
        
        # === CASINO MODE STATS ===
        self.starting_chips = 0
        self.current_chips = 0
        self.total_won = 0
        self.total_lost = 0
        self.biggest_win = 0
        self.biggest_loss = 0
        self.double_downs = 0
        self.double_downs_won = 0
        self.double_downs_lost = 0
        self.best_chip_balance = 0
        self.worst_chip_balance = 0
        
        # === BOT MODE STATS ===
        self.bot_decisions = 0
        self.bot_hits = 0
        self.bot_stands = 0
        self.bot_correct_predictions = 0
        
        # === CARD TRACKING ===
        self.cards_received = []
        self.aces_received = 0
        self.face_cards_received = 0
        self.low_cards_received = 0
        self.high_cards_received = 0
    
    def update_after_round(self, result, player_hand, dealer_hand, bet=0, doubled=False, actual_winnings=0):
        """Update all relevant stats after a round"""
        filtered_player_hand = [c for c in player_hand if c is not None]
        filtered_dealer_hand = [c for c in dealer_hand if c is not None]
        
        player_value = calculate_hand_value(filtered_player_hand)
        dealer_value = calculate_hand_value(filtered_dealer_hand)
        
        self.rounds_played += 1
        self.total_hand_value += player_value
        
        for card in filtered_player_hand:
            self.cards_received.append(card)
            if card.rank == 1:
                self.aces_received += 1
            elif card.rank >= 11:
                self.face_cards_received += 1
            elif card.rank <= 6:
                self.low_cards_received += 1
            else:
                self.high_cards_received += 1
        
        if result == RESULT_WIN:
            self.wins += 1
            self._update_streak(won=True)
            if dealer_value > 21:
                self.dealer_busts += 1
            else:
                self.times_beat_dealer += 1
            if bet > 0:
                # Use actual_winnings if provided, otherwise calculate
                if actual_winnings > 0:
                    winnings = actual_winnings
                else:
                    # Fallback calculation
                    is_blackjack = len(filtered_player_hand) == 2 and player_value == 21
                    if is_blackjack:
                        winnings = int(bet * BLACKJACK_MULTIPLIER) + bet
                    else:
                        winnings = bet * 2
                self.total_won += winnings
                self.biggest_win = max(self.biggest_win, winnings)
                if doubled:
                    self.double_downs_won += 1
        elif result == RESULT_LOSS:
            self.losses += 1
            self._update_streak(won=False)
            if player_value > 21:
                self.busts += 1
                self.biggest_bust = max(self.biggest_bust, player_value)
            else:
                self.times_lost_to_dealer += 1
            if bet > 0:
                # Loss is just the bet amount (already deducted)
                loss_amount = bet
                self.total_lost += loss_amount
                self.biggest_loss = max(self.biggest_loss, loss_amount)
                if doubled:
                    self.double_downs_lost += 1
        else:
            self.ties += 1
            self.current_streak = 0
        
        if player_value == 21:
            if len(filtered_player_hand) == 2:
                self.blackjacks += 1
            else:
                self.perfect_21s += 1
        if dealer_value == 21:
            if len(filtered_dealer_hand) == 2:
                self.dealer_blackjacks += 1
        if doubled:
            self.double_downs += 1
    
    def _update_streak(self, won):
        """Update win/lose streak"""
        if won:
            if self.current_streak >= 0:
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.longest_win_streak = max(self.longest_win_streak, self.current_streak)
        else:
            if self.current_streak <= 0:
                self.current_streak -= 1
            else:
                self.current_streak = -1
            self.longest_lose_streak = max(self.longest_lose_streak, abs(self.current_streak))
    
    def update_decision(self, decision, caused_bust=False):
        """Track hit/stand decisions"""
        if decision == "Hittt":
            self.total_hits += 1
            if caused_bust:
                self.hits_that_busted += 1
        else:
            self.total_stands += 1
    
    def update_chips(self, new_balance):
        """Track chip balance changes"""
        if self.starting_chips == 0:
            self.starting_chips = new_balance
            self.best_chip_balance = new_balance
            self.worst_chip_balance = new_balance
        self.current_chips = new_balance
        self.best_chip_balance = max(self.best_chip_balance, new_balance)
        self.worst_chip_balance = min(self.worst_chip_balance, new_balance)
    
    def to_dict(self, mode):
        """Convert stats to dictionary for JSON transmission"""
        win_rate = (self.wins / self.rounds_played * 100) if self.rounds_played > 0 else 0
        avg_hand = (self.total_hand_value / self.rounds_played) if self.rounds_played > 0 else 0
        
        stats = {
            'rounds_played': self.rounds_played,
            'wins': self.wins,
            'losses': self.losses,
            'ties': self.ties,
            'win_rate': win_rate,
            'avg_hand': avg_hand,
            'current_streak': self.current_streak,
            'longest_win_streak': self.longest_win_streak,
            'longest_lose_streak': self.longest_lose_streak,
            'blackjacks': self.blackjacks,
            'busts': self.busts,
            'biggest_bust': self.biggest_bust,
            'perfect_21s': self.perfect_21s,
            'total_hits': self.total_hits,
            'total_stands': self.total_stands,
            'hits_that_busted': self.hits_that_busted,
            'dealer_busts': self.dealer_busts,
            'dealer_blackjacks': self.dealer_blackjacks,
            'times_beat_dealer': self.times_beat_dealer,
            'times_lost_to_dealer': self.times_lost_to_dealer,
            'mode': mode
        }
        
        if mode == MODE_CASINO:
            profit = self.total_won - self.total_lost
            roi = ((self.current_chips - self.starting_chips) / self.starting_chips * 100) if self.starting_chips > 0 else 0
            stats.update({
                'starting_chips': self.starting_chips,
                'current_chips': self.current_chips,
                'best_chip_balance': self.best_chip_balance,
                'worst_chip_balance': self.worst_chip_balance,
                'total_won': self.total_won,
                'total_lost': self.total_lost,
                'profit': profit,
                'roi': roi,
                'biggest_win': self.biggest_win,
                'biggest_loss': self.biggest_loss,
                'double_downs': self.double_downs,
                'double_downs_won': self.double_downs_won,
                'double_downs_lost': self.double_downs_lost
            })
        elif mode == MODE_BOT:
            stats.update({
                'bot_decisions': self.bot_decisions,
                'bot_hits': self.bot_hits,
                'bot_stands': self.bot_stands,
                'aces_received': self.aces_received,
                'face_cards_received': self.face_cards_received,
                'high_cards_received': self.high_cards_received,
                'low_cards_received': self.low_cards_received
            })
        
        return stats


# ============================================================================
# Casino Mode Classes
# ============================================================================

class CasinoGame:
    """Manages casino mode game state"""
    
    def __init__(self):
        self.chips = STARTING_CHIPS
        self.current_bet = 0
    
    def can_double_down(self):
        """Check if player can double down"""
        return DOUBLE_DOWN_ENABLED and self.chips >= self.current_bet
    
    def double_down(self):
        """Double the current bet"""
        self.chips -= self.current_bet  # Deduct additional bet
        self.current_bet *= 2  # Double the bet
    
    def process_result(self, result, player_hand, dealer_value):
        """Process round result and update chips. Returns actual winnings amount."""
        player_value = calculate_hand_value([c for c in player_hand if c])
        is_blackjack = len([c for c in player_hand if c]) == 2 and player_value == 21
        
        actual_winnings = 0
        
        if result == RESULT_WIN:
            if is_blackjack:
                # Blackjack pays 1.5x plus original bet back
                winnings = int(self.current_bet * BLACKJACK_MULTIPLIER)
                self.chips += self.current_bet + winnings  # Return bet + winnings
                actual_winnings = self.current_bet + winnings
            else:
                # Regular win: return bet + equal winnings (2x total)
                self.chips += self.current_bet * 2
                actual_winnings = self.current_bet * 2
        elif result == RESULT_TIE:
            # Push - return the bet
            self.chips += self.current_bet
            actual_winnings = 0
        # On LOSS: do nothing, bet was already deducted at round start
        # actual_winnings remains 0
        
        self.current_bet = 0
        return actual_winnings


# ============================================================================
# Bot Mode Classes
# ============================================================================

class BlackjackBot:
    """Bot that plays Blackjack using Basic Strategy"""
    
    def __init__(self):
        self.decisions_made = 0
    
    def get_decision(self, player_hand, dealer_showing_card):
        """Get optimal decision based on Basic Strategy"""
        player_value = calculate_hand_value([c for c in player_hand if c])
        dealer_value = dealer_showing_card.get_value()
        has_soft_ace = self._has_soft_ace(player_hand)
        
        decision, reason = self._basic_strategy(player_value, dealer_value, has_soft_ace)
        self.decisions_made += 1
        return decision, reason
    
    def _has_soft_ace(self, hand):
        """Check if hand has a soft ace"""
        filtered_hand = [c for c in hand if c is not None]
        total = calculate_hand_value(filtered_hand)
        aces = sum(1 for card in filtered_hand if card.rank == 1)
        return aces > 0 and total <= 21
    
    def _basic_strategy(self, player_value, dealer_value, is_soft):
        """Implement Basic Strategy"""
        if player_value == 21:
            return ("Stand", "21 is perfect - always stand!")
        if player_value <= 8:
            return ("Hittt", "Low hand - always hit on 8 or less")
        if is_soft:
            if player_value >= 19:
                return ("Stand", "Soft 19+ - stand")
            elif player_value == 18:
                if dealer_value >= 9:
                    return ("Hittt", "Soft 18 vs high card - hit")
                else:
                    return ("Stand", "Soft 18 vs low card - stand")
            else:
                return ("Hittt", "Soft 17 or less - hit")
        if player_value >= 17:
            return ("Stand", "Hard 17+ - always stand")
        elif player_value >= 13:
            if dealer_value <= 6:
                return ("Stand", f"Hard {player_value} vs dealer {dealer_value} - stand")
            else:
                return ("Hittt", f"Hard {player_value} vs dealer {dealer_value} - hit")
        elif player_value == 12:
            if 4 <= dealer_value <= 6:
                return ("Stand", "Hard 12 vs dealer 4-6 - stand")
            else:
                return ("Hittt", "Hard 12 vs dealer 2-3 or 7+ - hit")
        elif player_value == 11:
            return ("Hittt", "11 is great for hitting!")
        elif player_value == 10:
            return ("Hittt", "10 vs dealer - hit")
        elif player_value == 9:
            return ("Hittt", "9 vs dealer - hit")
        return ("Hittt", "Basic strategy says hit")


# ============================================================================
# Network Functions
# ============================================================================

def receive_card(tcp_socket):
    """Receive card from server with retry logic"""
    max_retries = 3
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            data = b''
            while len(data) < 9:
                try:
                    chunk = tcp_socket.recv(9 - len(data))
                    if len(chunk) == 0:
                        raise ConnectionError("Connection closed by server")
                    data += chunk
                except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                    # WinError 10053 or similar connection errors
                    error_code = getattr(e, 'winerror', None) or getattr(e, 'errno', None)
                    if error_code == 10053:  # WinError 10053
                        print(f"[WARNING] Connection aborted (WinError 10053), attempt {attempt + 1}/{max_retries}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                    raise ConnectionError(f"Connection error: {str(e)}")
            
            parsed = parse_payload_server(data)
            if parsed is None:
                raise Exception("Invalid payload packet from server")
            
            result, card_rank, card_suit = parsed
            card = Card(card_rank, card_suit)
            return (result, card)
        except ConnectionError as e:
            if attempt < max_retries - 1:
                print(f"[WARNING] Connection error, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                continue
            else:
                print(f"[ERROR] receive_card failed after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            print(f"[ERROR] receive_card failed: {e}")
            raise


def send_decision(tcp_socket, decision):
    """Send decision to server with retry logic"""
    max_retries = 3
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            packet = create_payload_client(decision)
            tcp_socket.sendall(packet)
            return  # Success
        except (ConnectionResetError, ConnectionAbortedError, OSError, BrokenPipeError) as e:
            # WinError 10053 or similar connection errors
            error_code = getattr(e, 'winerror', None) or getattr(e, 'errno', None)
            if error_code == 10053:  # WinError 10053
                print(f"[WARNING] Connection aborted while sending (WinError 10053), attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
            if attempt < max_retries - 1:
                print(f"[WARNING] Connection error while sending, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                continue
            else:
                raise ConnectionError(f"Failed to send decision after {max_retries} attempts: {str(e)}")
        except Exception as e:
            print(f"[ERROR] send_decision failed: {e}")
            raise


# ============================================================================
# SocketIO Event Handlers
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('connected', {'status': 'ok', 'message': 'Connected to web server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    from flask import request
    session_id = request.sid
    if session_id in active_games:
        try:
            active_games[session_id]['socket'].close()
        except:
            pass
        del active_games[session_id]


@socketio.on('scan_servers')
def handle_scan():
    """Scan for servers via UDP"""
    servers = {}
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        try:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind(('', UDP_BROADCAST_PORT))
        udp_socket.settimeout(1.0)
        
        start_time = time.time()
        scan_duration = 3
        
        while time.time() - start_time < scan_duration:
            try:
                data, addr = udp_socket.recvfrom(1024)
                parsed = parse_offer_packet(data)
                if parsed:
                    tcp_port, server_name = parsed
                    servers[server_name] = (addr[0], tcp_port)
            except socket.timeout:
                continue
    finally:
        udp_socket.close()
    
    emit('servers_found', {'servers': servers})


@socketio.on('connect_to_server')
def handle_connect_to_server(data):
    """Connect to a server and start game"""
    from flask import request
    
    server_ip = data['ip']
    tcp_port = data['port']
    num_rounds = data.get('rounds', 1)
    game_mode = data.get('game_mode', MODE_CLASSIC)
    player_character = data.get('player_character', 'gaya')
    session_id = request.sid
    
    try:
        # Connect to server
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(30.0)
        tcp_socket.connect((server_ip, tcp_port))
        
        # Send request
        request_packet = create_request_packet(num_rounds, TEAM_NAME)
        tcp_socket.sendall(request_packet)
        
        # Initialize mode-specific objects
        casino_game = None
        bot = None
        if game_mode == MODE_CASINO:
            casino_game = CasinoGame()
        elif game_mode == MODE_BOT:
            bot = BlackjackBot()
        
        # Store connection
        active_games[session_id] = {
            'socket': tcp_socket,
            'my_hand': [],
            'dealer_hand': [],
            'round_num': 0,
            'num_rounds': num_rounds,
            'game_mode': game_mode,
            'player_character': player_character,
            'waiting_for_decision': False,
            'stats': GameStatistics(),
            'casino_game': casino_game,
            'bot': bot
        }
        
        if casino_game:
            active_games[session_id]['stats'].update_chips(casino_game.chips)
        
        emit('connected_to_game', {'status': 'success', 'rounds': num_rounds, 'game_mode': game_mode})
        
        # Start game thread
        threading.Thread(
            target=play_game_loop,
            args=(session_id, tcp_socket, num_rounds, game_mode),
            daemon=True
        ).start()
        
    except Exception as e:
        emit('error', {'message': f'Connection error: {str(e)}'})


def play_game_loop(session_id, tcp_socket, num_rounds, game_mode):
    """Main game loop in separate thread"""
    game_completed = False  # Track if game completed successfully
    try:
        print(f"[DEBUG] Starting game with {num_rounds} rounds, mode={game_mode}")
        
        # Verify session still exists
        if session_id not in active_games:
            print(f"[ERROR] Session {session_id} not found in active_games at start of play_game_loop")
            return
        
        stats = active_games[session_id]['stats']
        casino_game = active_games[session_id].get('casino_game')
        bot = active_games[session_id].get('bot')
        
        for round_num in range(1, num_rounds + 1):
            print(f"[DEBUG] ========== STARTING ROUND {round_num}/{num_rounds} ==========")
            if session_id not in active_games:
                break
            
            # Reset round state
            my_hand = []
            dealer_hand = []
            active_games[session_id]['doubled'] = False  # Reset doubled flag
            active_games[session_id]['last_decision'] = None
            player_busted = False  # Track if player busted
            
            # Emit round start
            socketio.emit('round_start', {'round': round_num, 'total': num_rounds}, room=session_id)
            time.sleep(0.3)
            
            # Casino mode: place bet
            if casino_game:
                # Check if player has enough chips to continue
                if casino_game.chips < MIN_BET:
                    print(f"[DEBUG] Player broke! Chips: {casino_game.chips}, Min bet: {MIN_BET}")
                    socketio.emit('game_over_broke', {
                        'chips': casino_game.chips,
                        'reason': 'insufficient_funds'
                    }, room=session_id)
                    break  # End game loop
                
                socketio.emit('place_bet', {
                    'chips': casino_game.chips,
                    'min_bet': MIN_BET,
                    'max_bet': min(MAX_BET, casino_game.chips)
                }, room=session_id)
                
                # Wait for bet
                while 'bet_amount' not in active_games[session_id] or active_games[session_id]['bet_amount'] is None:
                    time.sleep(0.1)
                    if session_id not in active_games:
                        return
                
                bet_amount = active_games[session_id].pop('bet_amount')
                casino_game.current_bet = bet_amount
                casino_game.chips -= bet_amount
                stats.update_chips(casino_game.chips)
            
            # Receive 2 cards for player
            for i in range(2):
                try:
                    result, card = receive_card(tcp_socket)
                    my_hand.append(card)
                except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, Exception) as e:
                    print(f"[ERROR] Failed to receive player card {i+1}: {e}")
                    socketio.emit('error', {
                        'message': f'Connection error: {str(e)}. Game will end.',
                        'fatal': True
                    }, room=session_id)
                    game_completed = False
                    return
                socketio.emit('card_received', {
                    'type': 'player',
                    'rank': card.rank,
                    'suit': card.suit,
                    'round': round_num
                }, room=session_id)
                time.sleep(0.3)
            
            # Receive 1 card for dealer (visible)
            try:
                result, dealer_visible_card = receive_card(tcp_socket)
                dealer_hand.append(dealer_visible_card)
            except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, Exception) as e:
                print(f"[ERROR] Failed to receive dealer card: {e}")
                socketio.emit('error', {
                    'message': f'Connection error: {str(e)}. Game will end.',
                    'fatal': True
                }, room=session_id)
                game_completed = False
                return
            socketio.emit('card_received', {
                'type': 'dealer',
                'rank': dealer_visible_card.rank,
                'suit': dealer_visible_card.suit,
                'hidden': False,
                'round': round_num
            }, room=session_id)
            time.sleep(0.3)
            
            # Placeholder for hidden card
            dealer_hand.append(None)
            socketio.emit('card_received', {
                'type': 'dealer',
                'hidden': True,
                'round': round_num
            }, room=session_id)
            
            # Update game state
            active_games[session_id]['my_hand'] = my_hand
            active_games[session_id]['dealer_hand'] = dealer_hand
            active_games[session_id]['round_num'] = round_num
            
            # Calculate values
            player_value = calculate_hand_value(my_hand)
            visible_dealer = [dealer_hand[0]] if dealer_hand else []
            dealer_visible_value = calculate_hand_value(visible_dealer) if visible_dealer else 0
            
            # Check for blackjack
            is_blackjack = len(my_hand) == 2 and player_value == 21
            
            socketio.emit('game_state', {
                'player_hand': [{'rank': c.rank, 'suit': c.suit} for c in my_hand],
                'dealer_hand': [{'rank': c.rank, 'suit': c.suit} if c else None for c in dealer_hand],
                'player_value': player_value,
                'dealer_value': dealer_visible_value,
                'dealer_hidden': True,
                'is_blackjack': is_blackjack,
                'round': round_num
            }, room=session_id)
            
            if is_blackjack:
                socketio.emit('blackjack', {}, room=session_id)
                time.sleep(1.5)
            
            # Player's turn
            if bot:
                # Bot mode: auto decision
                decision, reason = bot.get_decision(my_hand, dealer_visible_card)
                socketio.emit('bot_decision', {'decision': decision, 'reason': reason}, room=session_id)
                time.sleep(0.5)
                try:
                    send_decision(tcp_socket, decision)
                except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, BrokenPipeError, Exception) as e:
                    print(f"[ERROR] Failed to send bot decision: {e}")
                    socketio.emit('error', {'message': f'Connection error: {str(e)}'}, room=session_id)
                    return
                stats.update_decision(decision)
                
                if decision == "Hittt":
                    while True:
                        try:
                            result, card = receive_card(tcp_socket)
                        except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, Exception) as e:
                            print(f"[ERROR] Failed to receive bot card: {e}")
                            socketio.emit('error', {'message': f'Connection error: {str(e)}'}, room=session_id)
                            return
                        my_hand.append(card)
                        active_games[session_id]['my_hand'] = my_hand
                        player_value = calculate_hand_value(my_hand)
                        
                        socketio.emit('card_received', {
                            'type': 'player',
                            'rank': card.rank,
                            'suit': card.suit
                        }, room=session_id)
                        time.sleep(0.3)
                        
                        socketio.emit('game_state', {
                            'player_hand': [{'rank': c.rank, 'suit': c.suit} for c in my_hand],
                            'dealer_hand': [{'rank': c.rank, 'suit': c.suit} if c else None for c in dealer_hand],
                            'player_value': player_value,
                            'dealer_value': dealer_visible_value,
                            'dealer_hidden': True
                        }, room=session_id)
                        
                        if result != RESULT_NOT_OVER or player_value > 21:
                            break
                        
                        # Bot decides again
                        decision, reason = bot.get_decision(my_hand, dealer_visible_card)
                        socketio.emit('bot_decision', {'decision': decision, 'reason': reason}, room=session_id)
                        time.sleep(0.5)
                        if decision == "Stand":
                            try:
                                send_decision(tcp_socket, decision)
                            except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, BrokenPipeError, Exception) as e:
                                print(f"[ERROR] Failed to send bot stand: {e}")
                                socketio.emit('error', {'message': f'Connection error: {str(e)}'}, room=session_id)
                                return
                            stats.update_decision(decision)
                            break
                        try:
                            send_decision(tcp_socket, decision)
                        except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, BrokenPipeError, Exception) as e:
                            print(f"[ERROR] Failed to send bot decision: {e}")
                            socketio.emit('error', {'message': f'Connection error: {str(e)}'}, room=session_id)
                            return
                        stats.update_decision(decision, caused_bust=(player_value > 21))
            else:
                # ========== HUMAN PLAYER'S TURN ==========
                first_decision = True
                
                while True:
                    player_value = calculate_hand_value(my_hand)
                    
                    # Check if already busted (shouldn't happen on first iteration)
                    if player_value > 21:
                        player_busted = True
                        break
                    
                    # Wait for player decision
                    active_games[session_id]['waiting_for_decision'] = True
                    socketio.emit('your_turn', {
                        'can_double': first_decision and casino_game and casino_game.can_double_down()
                    }, room=session_id)
                    
                    # Wait for decision
                    while session_id in active_games and active_games[session_id]['waiting_for_decision']:
                        time.sleep(0.1)
                    
                    if session_id not in active_games:
                        return
                    
                    decision = active_games[session_id].get('last_decision')
                    active_games[session_id]['last_decision'] = None
                    first_decision = False
                    
                    if not decision:
                        break
                    
                    if decision == "Stand":
                        # Player stands - go to dealer turn
                        stats.update_decision("Stand")
                        break
                    
                    # Hit or DoubleDown - receive card
                    try:
                        result, card = receive_card(tcp_socket)
                        my_hand.append(card)
                        active_games[session_id]['my_hand'] = my_hand
                        
                        socketio.emit('card_received', {
                            'type': 'player',
                            'rank': card.rank,
                            'suit': card.suit
                        }, room=session_id)
                        time.sleep(0.3)
                        
                        player_value = calculate_hand_value(my_hand)
                        stats.update_decision("Hittt", caused_bust=(player_value > 21))
                        
                        socketio.emit('game_state', {
                            'player_hand': [{'rank': c.rank, 'suit': c.suit} for c in my_hand],
                            'dealer_hand': [{'rank': c.rank, 'suit': c.suit} if c else None for c in dealer_hand],
                            'player_value': player_value,
                            'dealer_value': dealer_visible_value,
                            'dealer_hidden': True
                        }, room=session_id)
                        
                        # Double down = one card then stand
                        if decision == "DoubleDown":
                            try:
                                send_decision(tcp_socket, "Stand")
                            except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, BrokenPipeError, Exception) as e:
                                print(f"[ERROR] Failed to send double down stand: {e}")
                                socketio.emit('error', {
                                    'message': f'Connection error: {str(e)}. Game will end.',
                                    'fatal': True
                                }, room=session_id)
                                game_completed = False
                                return
                            stats.update_decision("Stand")
                            break
                    except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, Exception) as e:
                        print(f"[ERROR] Failed to receive card after hit: {e}")
                        socketio.emit('error', {
                            'message': f'Connection error: {str(e)}. Game will end.',
                            'fatal': True
                        }, room=session_id)
                        game_completed = False
                        return
                    
                    # Check result
                    if result != RESULT_NOT_OVER or player_value > 21:
                        if player_value > 21:
                            player_busted = True
                            socketio.emit('bust', {'player_value': player_value}, room=session_id)
                        break
            
            # ========== HANDLE PLAYER BUST ==========
            if player_busted:
                dealer_value = calculate_hand_value([c for c in dealer_hand if c]) if dealer_hand else 0
                bet = casino_game.current_bet if casino_game else 0
                doubled = active_games[session_id].get('doubled', False)
                
                actual_winnings = 0
                if casino_game:
                    actual_winnings = casino_game.process_result(RESULT_LOSS, my_hand, dealer_value)
                    stats.update_chips(casino_game.chips)
                    
                    # Check if player broke after this round
                    if casino_game.chips < MIN_BET:
                        print(f"[DEBUG] Player broke after round {round_num}! Chips: {casino_game.chips}")
                        socketio.emit('game_over_broke', {
                            'chips': casino_game.chips,
                            'reason': 'insufficient_funds',
                            'round': round_num
                        }, room=session_id)
                        break  # End game loop
                
                stats.update_after_round(RESULT_LOSS, my_hand, dealer_hand, bet, doubled, actual_winnings)
                
                socketio.emit('round_over', {
                    'result': 'loss',
                    'player_value': player_value,
                    'dealer_value': dealer_value,
                    'reason': 'bust',
                    'round': round_num
                }, room=session_id)
                
                socketio.emit('mini_stats', stats.to_dict(game_mode), room=session_id)
                
                if round_num < num_rounds:
                    socketio.emit('next_round', {
                        'current': round_num,
                        'next': round_num + 1,
                        'total': num_rounds
                    }, room=session_id)
                    time.sleep(2)  # Give frontend time to show result
                
                print(f"[DEBUG] ========== ROUND {round_num} COMPLETE (BUST) ==========")
                continue  # Next round!
            
            # Dealer's turn - fast, no delays
            socketio.emit('dealer_turn', {}, room=session_id)
            
            # Receive dealer's cards - process immediately, no delays
            while True:
                try:
                    result, card = receive_card(tcp_socket)
                except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, Exception) as e:
                    print(f"[ERROR] Failed to receive dealer card: {e}")
                    socketio.emit('error', {
                        'message': f'Connection error: {str(e)}. Game will end.',
                        'fatal': True
                    }, room=session_id)
                    game_completed = False
                    return
                
                if result == RESULT_NOT_OVER:
                    # Replace hidden card or add new card
                    if len(dealer_hand) == 2 and dealer_hand[1] is None:
                        dealer_hand[1] = card
                        socketio.emit('reveal_hidden_card', {
                            'rank': card.rank,
                            'suit': card.suit
                        }, room=session_id)
                    else:
                        dealer_hand.append(card)
                        socketio.emit('card_received', {
                            'type': 'dealer',
                            'rank': card.rank,
                            'suit': card.suit,
                            'hidden': False
                        }, room=session_id)
                    
                    active_games[session_id]['dealer_hand'] = dealer_hand
                    # No delay - process immediately
                else:
                    # Final result
                    dealer_value = calculate_hand_value([c for c in dealer_hand if c])
                    player_value = calculate_hand_value(my_hand)
                    
                    if result == RESULT_WIN:
                        result_text = 'win'
                    elif result == RESULT_LOSS:
                        result_text = 'loss'
                    else:
                        result_text = 'tie'
                    
                    # Update stats
                    bet = casino_game.current_bet if casino_game else 0
                    doubled = active_games[session_id].get('doubled', False)
                    
                    actual_winnings = 0
                    if casino_game:
                        actual_winnings = casino_game.process_result(result, my_hand, dealer_value)
                        stats.update_chips(casino_game.chips)
                        
                        # Check if player broke after this round
                        if casino_game.chips < MIN_BET:
                            print(f"[DEBUG] Player broke after round {round_num}! Chips: {casino_game.chips}")
                            socketio.emit('game_over_broke', {
                                'chips': casino_game.chips,
                                'reason': 'insufficient_funds',
                                'round': round_num
                            }, room=session_id)
                            break  # End game loop
                    
                    stats.update_after_round(result, my_hand, dealer_hand, bet, doubled, actual_winnings)
                    
                    socketio.emit('round_over', {
                        'result': result_text,
                        'player_value': player_value,
                        'dealer_value': dealer_value,
                        'round': round_num
                    }, room=session_id)
                    break
            
            # Mini stats after round
            socketio.emit('mini_stats', stats.to_dict(game_mode), room=session_id)
            
            if round_num < num_rounds:
                socketio.emit('next_round', {
                    'current': round_num,
                    'next': round_num + 1,
                    'total': num_rounds
                }, room=session_id)
                time.sleep(2)  # Give frontend time to show result
            
            print(f"[DEBUG] ========== ROUND {round_num} COMPLETE ==========")
        
        # Game finished - send full stats
        print(f"[DEBUG] ========== GAME FINISHED ==========")
        game_completed = True  # Mark game as completed successfully
        
        if session_id not in active_games:
            print(f"[WARNING] Session {session_id} not in active_games at game finish")
            return
        
        final_stats = stats.to_dict(game_mode)
        print(f"[DEBUG] Final stats: {final_stats}")
        
        # Check if game ended due to insufficient funds
        broke = False
        if casino_game and casino_game.chips < MIN_BET:
            broke = True
            print(f"[DEBUG] Game ended because player broke (chips: {casino_game.chips})")
        
        socketio.emit('game_finished', {
            'stats': final_stats,
            'game_mode': game_mode,
            'total_rounds': num_rounds,
            'show_stats': True,
            'broke': broke
        }, room=session_id)
        
        # Also emit to ensure it's received
        time.sleep(1)
        socketio.emit('show_final_stats', final_stats, room=session_id)
        
    except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError) as e:
        error_msg = f"Connection error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        if session_id in active_games:
            try:
                socketio.emit('error', {'message': error_msg}, room=session_id)
            except:
                pass
    except Exception as e:
        error_msg = f"Game error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        if session_id in active_games:
            try:
                socketio.emit('error', {'message': error_msg}, room=session_id)
            except:
                pass
    finally:
        # Only clean up if game completed or session is invalid
        if session_id in active_games:
            # Only delete if game completed successfully or if there's an error
            if game_completed:
                print(f"[DEBUG] Cleaning up session {session_id} after game completion")
                try:
                    tcp_socket = active_games[session_id].get('socket')
                    if tcp_socket:
                        try:
                            tcp_socket.shutdown(socket.SHUT_RDWR)
                        except:
                            pass
                        try:
                            tcp_socket.close()
                        except:
                            pass
                except Exception as e:
                    print(f"[ERROR] Error closing socket: {e}")
                try:
                    del active_games[session_id]
                    print(f"[DEBUG] Session {session_id} removed from active_games")
                except:
                    pass
            else:
                # Game didn't complete - might still be running, don't delete yet
                print(f"[WARNING] Game loop ended but game_completed=False for session {session_id}")
                # Still close socket but keep session for now
                try:
                    tcp_socket = active_games[session_id].get('socket')
                    if tcp_socket:
                        try:
                            tcp_socket.shutdown(socket.SHUT_RDWR)
                        except:
                            pass
                        try:
                            tcp_socket.close()
                        except:
                            pass
                except Exception as e:
                    print(f"[ERROR] Error closing socket: {e}")


@socketio.on('player_decision')
def handle_decision(data):
    """Handle player decision (Hit/Stand/DoubleDown)"""
    from flask import request
    
    session_id = request.sid
    decision = data['decision']  # "Hittt", "Stand", or "DoubleDown"
    
    if session_id not in active_games:
        print(f"[WARNING] handle_decision: No active game for session {session_id}")
        emit('error', {'message': 'No active game. Please reconnect.'})
        return
    
    if 'waiting_for_decision' not in active_games[session_id]:
        print(f"[WARNING] handle_decision: waiting_for_decision not set for session {session_id}")
        emit('error', {'message': 'Game not ready. Please wait.'})
        return
    
    if not active_games[session_id]['waiting_for_decision']:
        emit('error', {'message': 'Not your turn'})
        return
    
    tcp_socket = active_games[session_id]['socket']
    casino_game = active_games[session_id].get('casino_game')
    stats = active_games[session_id]['stats']
    
    try:
        if decision == "DoubleDown" and casino_game:
            casino_game.double_down()
            active_games[session_id]['doubled'] = True
        
        # Send decision to server
        try:
            send_decision(tcp_socket, "Hittt" if decision == "DoubleDown" else decision)
        except (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError, BrokenPipeError, Exception) as e:
            print(f"[ERROR] Failed to send decision: {e}")
            emit('error', {
                'message': f'Connection error: {str(e)}. Please try again.',
                'fatal': False
            })
            # Don't return - let the game continue, the decision might have been sent
            return
        
        # Don't update stats here - play_game_loop handles it with caused_bust parameter
        
        # Store decision and clear waiting flag - play_game_loop will handle receiving cards
        active_games[session_id]['last_decision'] = decision
        active_games[session_id]['waiting_for_decision'] = False
        
        socketio.emit('decision_made', {'decision': decision}, room=session_id)
        
    except Exception as e:
        emit('error', {'message': str(e)})
        active_games[session_id]['waiting_for_decision'] = False


@socketio.on('place_bet')
def handle_place_bet(data):
    """Handle bet placement in casino mode"""
    from flask import request
    session_id = request.sid
    
    if session_id not in active_games:
        print(f"[WARNING] handle_place_bet: No active game for session {session_id}")
        emit('error', {'message': 'No active game. Please reconnect.'})
        return
    
    bet_amount = data.get('bet')
    if bet_amount is None:
        emit('error', {'message': 'No bet amount provided'})
        return
    
    active_games[session_id]['bet_amount'] = bet_amount


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/assests/<path:filename>')
def serve_assets(filename):
    """Serve images from assests directory"""
    from flask import send_from_directory
    import os
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assests')
    return send_from_directory(assets_dir, filename)


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🎰 BLACKJACK WEB CLIENT - Professional Edition")
    print("="*70)
    print("🌐 Server starting on http://127.0.0.1:5000")
    print("📱 Open your browser and navigate to the URL above")
    print("="*70 + "\n")
    socketio.run(app, host='127.0.0.1', port=5000, debug=True, allow_unsafe_werkzeug=True)
