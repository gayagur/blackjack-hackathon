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
from game_logic import Card, calculate_hand_value, is_bust, Deck
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
    MODE_MULTIPLAYER,
    STARTING_CHIPS,
    MIN_BET,
    MAX_BET,
    BLACKJACK_MULTIPLIER,
    DOUBLE_DOWN_ENABLED,
    MAX_PLAYERS_PER_ROOM,
    MIN_PLAYERS_TO_START
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blackjack-professional-2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Store active game connections
active_games = {}

# Multiplayer room management
game_rooms = {}  # room_id -> RoomState
player_rooms = {}  # session_id -> room_id


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
# Multiplayer Mode Classes
# ============================================================================

class PlayerState:
    """State for a single player in multiplayer"""
    def __init__(self, session_id, name, character):
        self.session_id = session_id
        self.name = name
        self.character = character
        self.hand = []
        self.hand_value = 0
        self.status = 'waiting'  # waiting, playing, stand, bust, done
        self.result = None  # win, loss, tie
        self.chips = STARTING_CHIPS  # for casino multiplayer
        self.current_bet = 0
        self.bet_placed = False  # Track if bet has been placed
        self.is_ready = False
        self.pending_decision = None  # Store decision from handler (Hit/Stand)


class RoomState:
    """Manages a multiplayer game room"""
    def __init__(self, room_id, host_session_id, num_rounds, is_casino=False):
        import threading
        self.room_id = room_id
        self.host_session_id = host_session_id
        self.players = {}  # session_id -> PlayerState
        self.dealer_hand = []
        self.dealer_value = 0
        self.current_turn_index = 0
        self.player_order = []  # list of session_ids in turn order
        self.round_num = 0
        self.num_rounds = num_rounds
        self.game_status = 'lobby'  # lobby, betting, playing, dealer_turn, round_over, finished
        self.is_casino = is_casino
        self.created_at = time.time()
        self.tcp_socket = None  # Connection to game server (not used for multiplayer cards)
        self.tcp_lock = threading.Lock()  # Lock for TCP socket access
        self.deck = None  # Local deck for multiplayer (created each round)
        self.dealer_hidden_card = None  # Store hidden dealer card
        self.stats = {}  # session_id -> GameStatistics
        # Server info (selected by host during room creation)
        self.server_ip = None
        self.server_port = None
        self.server_name = None
    
    def add_player(self, session_id, name, character):
        if len(self.players) >= MAX_PLAYERS_PER_ROOM:
            return False
        self.players[session_id] = PlayerState(session_id, name, character)
        self.player_order.append(session_id)
        self.stats[session_id] = GameStatistics()
        return True
    
    def remove_player(self, session_id):
        if session_id in self.players:
            del self.players[session_id]
            if session_id in self.player_order:
                self.player_order.remove(session_id)
            if session_id in self.stats:
                del self.stats[session_id]
    
    def get_current_player(self):
        if self.current_turn_index < len(self.player_order):
            return self.players.get(self.player_order[self.current_turn_index])
        return None
    
    def next_turn(self):
        self.current_turn_index += 1
        return self.current_turn_index < len(self.player_order)
    
    def all_players_ready(self):
        return all(p.is_ready for p in self.players.values())
    
    def all_players_done(self):
        return all(p.status in ['stand', 'bust', 'done'] for p in self.players.values())
    
    def reset_for_new_round(self):
        self.dealer_hand = []
        self.dealer_value = 0
        self.dealer_hidden_card = None
        self.current_turn_index = 0
        self.deck = Deck()  # Fresh shuffled deck each round
        for player in self.players.values():
            player.hand = []
            player.hand_value = 0
            player.status = 'waiting'
            player.result = None
            player.is_ready = False
            player.current_bet = 0
            player.bet_placed = False
            player.pending_decision = None  # Reset pending decision
    
    def to_dict(self):
        """Convert room state to dictionary for sending to clients"""
        return {
            'room_id': self.room_id,
            'players': {
                sid: {
                    'name': p.name,
                    'character': p.character,
                    'hand': [{'rank': c.rank, 'suit': c.suit} for c in p.hand] if p.hand else [],
                    'hand_value': p.hand_value,
                    'status': p.status,
                    'result': p.result,
                    'chips': p.chips,
                    'current_bet': p.current_bet,
                    'is_ready': p.is_ready,
                    'bet_placed': p.bet_placed
                }
                for sid, p in self.players.items()
            },
            'dealer_hand': [
                {'rank': c.rank, 'suit': c.suit} if c and (i == 0 or self.game_status in ['dealer_turn', 'round_over', 'finished']) else None 
                for i, c in enumerate(self.dealer_hand)
            ],
            'dealer_value': self.dealer_value,
            'current_turn': self.player_order[self.current_turn_index] if self.current_turn_index < len(self.player_order) else None,
            'player_order': self.player_order,
            'round_num': self.round_num,
            'num_rounds': self.num_rounds,
            'game_status': self.game_status,
            'player_count': len(self.players),
            'max_players': MAX_PLAYERS_PER_ROOM,
            'is_casino': self.is_casino,
            'server_ip': self.server_ip,
            'server_port': self.server_port,
            'server_name': self.server_name,
            'stats': {
                sid: stats.to_dict(MODE_CASINO if self.is_casino else MODE_MULTIPLAYER)
                for sid, stats in self.stats.items()
            } if self.stats else {}
        }


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


# ============================================================================
# Multiplayer Socket Handlers
# ============================================================================

import uuid
from flask_socketio import join_room, leave_room

@socketio.on('create_room')
def handle_create_room(data):
    """Host creates a new multiplayer room"""
    from flask import request
    session_id = request.sid
    
    room_id = str(uuid.uuid4())[:8].upper()  # Short room code like "A1B2C3D4"
    num_rounds = data.get('rounds', 5)
    is_casino = data.get('is_casino', False)
    player_name = data.get('player_name', 'Player 1')
    character = data.get('character', 'gaya')
    
    # Get server info from host
    server_ip = data.get('server_ip')
    server_port = data.get('server_port')
    server_name = data.get('server_name')
    
    if not server_ip or not server_port:
        emit('error', {'message': 'Please select a server first'})
        return
    
    room = RoomState(room_id, session_id, num_rounds, is_casino)
    room.server_ip = server_ip
    room.server_port = server_port
    room.server_name = server_name
    room.add_player(session_id, player_name, character)
    
    game_rooms[room_id] = room
    player_rooms[session_id] = room_id
    
    # Join socket.io room for broadcasting
    join_room(room_id)
    
    emit('room_created', {
        'room_id': room_id,
        'room_state': room.to_dict()
    })
    
    print(f"[MULTIPLAYER] Room {room_id} created by {player_name} on server {server_name}")


@socketio.on('join_room')
def handle_join_room(data):
    """Player joins an existing room"""
    from flask import request
    session_id = request.sid
    
    room_id = data.get('room_id', '').upper()
    player_name = data.get('player_name', 'Player')
    character = data.get('character', 'gaya')
    
    if room_id not in game_rooms:
        emit('error', {'message': 'Room not found'})
        return
    
    room = game_rooms[room_id]
    
    if room.game_status != 'lobby':
        emit('error', {'message': 'Game already in progress'})
        return
    
    if len(room.players) >= MAX_PLAYERS_PER_ROOM:
        emit('error', {'message': 'Room is full'})
        return
    
    # Add player to room
    if not room.add_player(session_id, player_name, character):
        emit('error', {'message': 'Failed to join room'})
        return
    
    player_rooms[session_id] = room_id
    
    # Join socket.io room
    join_room(room_id)
    
    # Also send room_state to the joining player
    emit('room_joined', {
        'room_state': room.to_dict()
    })
    
    # Notify everyone in room (including the new player)
    socketio.emit('player_joined', {
        'player_name': player_name,
        'character': character,
        'room_state': room.to_dict()
    }, room=room_id)
    
    print(f"[MULTIPLAYER] {player_name} joined room {room_id}")


@socketio.on('leave_room')
def handle_leave_room():
    """Player leaves the room - works during lobby AND during game"""
    from flask import request
    session_id = request.sid
    
    if session_id not in player_rooms:
        return
    
    room_id = player_rooms[session_id]
    room = game_rooms.get(room_id)
    
    if room:
        player = room.players.get(session_id)
        player_name = player.name if player else 'Unknown'
        
        print(f"[MULTIPLAYER] {player_name} leaving room {room_id}")
        
        # If game is in progress, mark player as disconnected
        if room.game_status not in ['lobby', 'finished']:
            if player:
                player.status = 'disconnected'
                player.result = 'loss'  # Forfeit
            
            socketio.emit('player_disconnected', {
                'player_name': player_name,
                'player_id': session_id,
                'room_state': room.to_dict()
            }, room=room_id)
        
        # Remove player
        room.remove_player(session_id)
        leave_room(room_id)
        del player_rooms[session_id]
        
        # If host left
        if session_id == room.host_session_id:
            if room.players:
                # Assign new host
                room.host_session_id = list(room.players.keys())[0]
                new_host = room.players[room.host_session_id]
                
                socketio.emit('new_host', {
                    'host_id': room.host_session_id,
                    'host_name': new_host.name,
                    'room_state': room.to_dict()
                }, room=room_id)
                
                print(f"[MULTIPLAYER] New host: {new_host.name}")
            else:
                # No players left - close room
                del game_rooms[room_id]
                print(f"[MULTIPLAYER] Room {room_id} deleted (empty)")
                return
        
        socketio.emit('player_left', {
            'player_name': player_name,
            'room_state': room.to_dict()
        }, room=room_id)
        
        # If only 1 player left during game, end the game
        if len(room.players) < MIN_PLAYERS_TO_START and room.game_status not in ['lobby', 'finished']:
            room.game_status = 'finished'
            socketio.emit('game_ended_not_enough_players', {
                'message': 'Not enough players to continue',
                'room_state': room.to_dict()
            }, room=room_id)


@socketio.on('player_ready')
def handle_player_ready(data):
    """Player signals they're ready to start"""
    from flask import request
    session_id = request.sid
    
    if session_id not in player_rooms:
        return
    
    room_id = player_rooms[session_id]
    room = game_rooms.get(room_id)
    
    if room and session_id in room.players:
        room.players[session_id].is_ready = data.get('ready', True)
        
        socketio.emit('player_ready_update', {
            'room_state': room.to_dict()
        }, room=room_id)
        
        # Check if all players ready and enough players
        if room.all_players_ready() and len(room.players) >= MIN_PLAYERS_TO_START:
            socketio.emit('all_players_ready', {}, room=room_id)


@socketio.on('start_multiplayer_game')
def handle_start_multiplayer(data):
    """Host starts the multiplayer game - NO TCP CONNECTION NEEDED (uses local deck)"""
    from flask import request
    session_id = request.sid
    
    if session_id not in player_rooms:
        emit('error', {'message': 'Not in a room'})
        return
    
    room_id = player_rooms[session_id]
    room = game_rooms.get(room_id)
    
    if not room:
        emit('error', {'message': 'Room not found'})
        return
    
    if session_id != room.host_session_id:
        emit('error', {'message': 'Only host can start the game'})
        return
    
    if len(room.players) < MIN_PLAYERS_TO_START:
        emit('error', {'message': f'Need at least {MIN_PLAYERS_TO_START} players'})
        return
    
    if not room.all_players_ready():
        emit('error', {'message': 'All players must be ready'})
        return
    
    # NO TCP connection needed for multiplayer!
    # We use local Deck instead
    
    room.game_status = 'playing'
    
    socketio.emit('multiplayer_game_started', {
        'room_state': room.to_dict()
    }, room=room_id)
    
    # Start game loop
    threading.Thread(
        target=multiplayer_game_loop,
        args=(room_id,),
        daemon=True
    ).start()


def multiplayer_game_loop(room_id):
    """Main game loop for multiplayer - FIXED VERSION"""
    room = game_rooms.get(room_id)
    if not room:
        print(f"[ERROR] Room {room_id} not found")
        return
    
    print(f"[MULTIPLAYER] Starting game loop for room {room_id}")
    
    try:
        for round_num in range(1, room.num_rounds + 1):
            print(f"[MULTIPLAYER] ========== ROUND {round_num}/{room.num_rounds} ==========")
            
            room.round_num = round_num
            room.reset_for_new_round()
            
            # Notify round start
            socketio.emit('multiplayer_round_start', {
                'round': round_num,
                'total': room.num_rounds,
                'room_state': room.to_dict()
            }, room=room_id)
            time.sleep(0.0)  # Instant - no delay
            
            # ========== CASINO MODE: COLLECT BETS ==========
            if room.is_casino:
                room.game_status = 'betting'
                
                # Reset bets for all players
                for player in room.players.values():
                    player.current_bet = 0
                    player.bet_placed = False
                
                # Send betting phase with chip info for each player
                betting_info = {}
                for sid, player in room.players.items():
                    betting_info[sid] = {
                        'chips': player.chips,
                        'min_bet': MIN_BET,
                        'max_bet': min(MAX_BET, player.chips),
                        'can_play': player.chips >= MIN_BET
                    }
                
                socketio.emit('multiplayer_betting_phase', {
                    'round': round_num,
                    'total_rounds': room.num_rounds,
                    'betting_info': betting_info,
                    'room_state': room.to_dict()
                }, room=room_id)
                
                # Wait for all players to place bets (with timeout)
                timeout = time.time() + 45  # 45 seconds to place bets
                
                while not all(p.bet_placed for p in room.players.values() if p.chips >= MIN_BET):
                    # Check if all players who can bet have bet - start immediately
                    can_bet_players = [p for p in room.players.values() if p.chips >= MIN_BET]
                    if can_bet_players and all(p.bet_placed for p in can_bet_players):
                        print(f"[MULTIPLAYER] All players bet! Starting immediately...")
                        break
                    
                    if time.time() > timeout:
                        # Auto-bet minimum for players who didn't bet
                        for player in room.players.values():
                            if not player.bet_placed and player.chips >= MIN_BET:
                                player.current_bet = MIN_BET
                                player.chips -= MIN_BET
                                player.bet_placed = True
                                print(f"[MULTIPLAYER] Auto-bet {MIN_BET} for {player.name}")
                        break
                    time.sleep(0.1)
                    if room_id not in game_rooms:
                        return
                
                # Announce all bets placed
                socketio.emit('multiplayer_all_bets_placed', {
                    'room_state': room.to_dict()
                }, room=room_id)
                time.sleep(0.0)  # Instant - no delay
            
            # ========== DEAL CARDS - LOCAL DECK (NO TCP!) ==========
            room.game_status = 'dealing'
            print(f"[MULTIPLAYER] Dealing cards from LOCAL deck to {len(room.players)} players")
            
            socketio.emit('multiplayer_dealing_started', {
                'room_state': room.to_dict()
            }, room=room_id)
            
            # Deal 2 cards to each player from LOCAL deck
            for player_sid in room.player_order:
                player = room.players.get(player_sid)
                if not player:
                    continue
                
                # Draw from LOCAL deck - instant, no TCP!
                card1 = room.deck.draw()
                card2 = room.deck.draw()
                player.hand = [card1, card2]
                player.hand_value = calculate_hand_value(player.hand)
                print(f"[MULTIPLAYER] Dealt {card1.rank}/{card1.suit}, {card2.rank}/{card2.suit} to {player.name}")
            
            # Deal dealer cards from LOCAL deck
            dealer_card1 = room.deck.draw()  # Visible
            dealer_card2 = room.deck.draw()  # Hidden (stored but not shown)
            room.dealer_hand = [dealer_card1, None]  # Second card hidden for now
            room.dealer_value = dealer_card1.get_value()  # Only visible card value
            room.dealer_hidden_card = dealer_card2  # Store for later reveal
            print(f"[MULTIPLAYER] Dealer: {dealer_card1.rank}/{dealer_card1.suit} (hidden: {dealer_card2.rank}/{dealer_card2.suit})")
            
            # Send all cards at once - INSTANT!
            socketio.emit('multiplayer_all_cards_dealt', {
                'room_state': room.to_dict()
            }, room=room_id)
            
            # Also send dealer card event
            socketio.emit('multiplayer_dealer_cards_dealt', {
                'room_state': room.to_dict()
            }, room=room_id)
            
            # Check for blackjacks
            for player_sid in room.player_order:
                player = room.players.get(player_sid)
                if player and player.hand_value == 21 and len(player.hand) == 2:
                    player.status = 'blackjack'
                    print(f"[MULTIPLAYER] {player.name} has BLACKJACK!")
                    socketio.emit('multiplayer_player_blackjack', {
                        'player_id': player_sid,
                        'room_state': room.to_dict()
                    }, room=room_id)
            
            # Game ready - start immediately
            room.game_status = 'playing'
            socketio.emit('multiplayer_dealing_complete', {
                'room_state': room.to_dict()
            }, room=room_id)
            
            # ========== EACH PLAYER'S TURN ==========
            room.current_turn_index = 0
            
            for i, player_sid in enumerate(room.player_order):
                if room_id not in game_rooms:
                    return
                
                player = room.players.get(player_sid)
                if not player:
                    continue
                
                room.current_turn_index = i
                
                # Skip if player has blackjack or already busted
                if player.status in ['blackjack', 'bust', 'stand']:
                    print(f"[MULTIPLAYER] Skipping {player.name} - status: {player.status}")
                    continue
                
                player.status = 'playing'
                
                # Notify whose turn
                print(f"[MULTIPLAYER] {player.name}'s turn")
                socketio.emit('multiplayer_player_turn', {
                    'player_id': player_sid,
                    'player_name': player.name,
                    'room_state': room.to_dict()
                }, room=room_id)
                
                # Wait for player decisions
                timeout = time.time() + 60  # 60 second timeout per player
                
                while player.status == 'playing':
                    # Check for pending decision from handler
                    if player.pending_decision:
                        decision = player.pending_decision
                        player.pending_decision = None  # Clear it
                        
                        print(f"[MULTIPLAYER] Processing {player.name}'s decision: {decision}")
                        
                        if decision == 'Stand':
                            player.status = 'stand'
                            socketio.emit('multiplayer_player_stand', {
                                'player_id': player_sid,
                                'room_state': room.to_dict()
                            }, room=room_id)
                            break
                        
                        elif decision == 'Hittt':
                            # Draw from LOCAL deck - instant!
                            card = room.deck.draw()
                            player.hand.append(card)
                            player.hand_value = calculate_hand_value(player.hand)
                            
                            print(f"[MULTIPLAYER] {player.name} hit: {card.rank}/{card.suit}, value: {player.hand_value}")
                            
                            if player.hand_value > 21:
                                player.status = 'bust'
                                socketio.emit('multiplayer_player_bust', {
                                    'player_id': player_sid,
                                    'card': {'rank': card.rank, 'suit': card.suit},
                                    'hand_value': player.hand_value,
                                    'room_state': room.to_dict()
                                }, room=room_id)
                                break
                            else:
                                socketio.emit('multiplayer_player_hit', {
                                    'player_id': player_sid,
                                    'card': {'rank': card.rank, 'suit': card.suit},
                                    'hand_value': player.hand_value,
                                    'room_state': room.to_dict()
                                }, room=room_id)
                                
                                # IMPORTANT: Emit turn again so player can continue
                                socketio.emit('multiplayer_player_turn', {
                                    'player_id': player_sid,
                                    'player_name': player.name,
                                    'room_state': room.to_dict()
                                }, room=room_id)
                    
                    if time.time() > timeout:
                        # Timeout - auto stand
                        print(f"[MULTIPLAYER] {player.name} timed out - auto stand")
                        player.status = 'stand'
                        socketio.emit('multiplayer_player_timeout', {
                            'player_id': player_sid,
                            'room_state': room.to_dict()
                        }, room=room_id)
                        break
                    
                    time.sleep(0.1)
                    if room_id not in game_rooms:
                        return
                
                print(f"[MULTIPLAYER] {player.name} finished - status: {player.status}")
            
            # ========== DEALER'S TURN - LOCAL DECK ==========
            room.game_status = 'dealer_turn'
            
            # Check if all players busted
            all_busted = all(p.status == 'bust' for p in room.players.values())
            
            if all_busted:
                print(f"[MULTIPLAYER] All players busted - skipping dealer turn")
                # Just reveal hidden card, don't draw more
                room.dealer_hand[1] = room.dealer_hidden_card
                room.dealer_value = calculate_hand_value([c for c in room.dealer_hand if c])
                
                socketio.emit('multiplayer_dealer_reveal', {
                    'card': {'rank': room.dealer_hidden_card.rank, 'suit': room.dealer_hidden_card.suit},
                    'room_state': room.to_dict()
                }, room=room_id)
                # Wait for players to see the revealed card
                time.sleep(3.0)
            else:
                # Normal dealer turn
                socketio.emit('multiplayer_dealer_turn', {
                    'room_state': room.to_dict()
                }, room=room_id)
                time.sleep(0.3)
                
                # Reveal hidden card
                room.dealer_hand[1] = room.dealer_hidden_card
                room.dealer_value = calculate_hand_value([c for c in room.dealer_hand if c])
                
                socketio.emit('multiplayer_dealer_reveal', {
                    'card': {'rank': room.dealer_hidden_card.rank, 'suit': room.dealer_hidden_card.suit},
                    'room_state': room.to_dict()
                }, room=room_id)
                # Wait for players to see the revealed card before dealer continues
                time.sleep(3.0)
                
                # Dealer hits until 17+ (from LOCAL deck)
                while room.dealer_value < 17:
                    card = room.deck.draw()
                    room.dealer_hand.append(card)
                    room.dealer_value = calculate_hand_value([c for c in room.dealer_hand if c])
                    
                    print(f"[MULTIPLAYER] Dealer hit: {card.rank}/{card.suit}, value: {room.dealer_value}")
                    
                    socketio.emit('multiplayer_dealer_hit', {
                        'card': {'rank': card.rank, 'suit': card.suit},
                        'dealer_value': room.dealer_value,
                        'room_state': room.to_dict()
                    }, room=room_id)
                    time.sleep(0.3)
            
            # Send dealer's final hand to all players
            socketio.emit('multiplayer_dealer_done', {
                'dealer_hand': [{'rank': c.rank, 'suit': c.suit} if c else None for c in room.dealer_hand],
                'dealer_value': room.dealer_value,
                'room_state': room.to_dict()
            }, room=room_id)
            
            # Wait 3 seconds so players can see the dealer's cards
            print(f"[MULTIPLAYER] Waiting 3 seconds for players to see dealer cards...")
            time.sleep(3)
            
            # ========== CALCULATE RESULTS ==========
            room.game_status = 'round_over'
            dealer_final = calculate_hand_value([c for c in room.dealer_hand if c])
            dealer_busted = dealer_final > 21
            
            print(f"[MULTIPLAYER] Calculating results - Dealer: {dealer_final}, Busted: {dealer_busted}")
            
            for player_sid in room.player_order:
                player = room.players.get(player_sid)
                if not player:
                    continue
                
                # Determine result
                if player.status == 'bust':
                    player.result = 'loss'
                elif dealer_busted:
                    player.result = 'win'
                elif player.hand_value > dealer_final:
                    player.result = 'win'
                elif player.hand_value < dealer_final:
                    player.result = 'loss'
                else:
                    player.result = 'tie'
                
                print(f"[MULTIPLAYER] {player.name}: {player.hand_value} vs Dealer {dealer_final} = {player.result}")
                
                # Update chips for casino mode
                if room.is_casino:
                    if player.result == 'win':
                        is_blackjack = player.status == 'blackjack'
                        if is_blackjack:
                            winnings = int(player.current_bet * BLACKJACK_MULTIPLIER) + player.current_bet
                        else:
                            winnings = player.current_bet * 2
                        player.chips += winnings
                    elif player.result == 'tie':
                        player.chips += player.current_bet  # Return bet
                    # Loss: bet already deducted
                
                # Update stats
                result_code = RESULT_WIN if player.result == 'win' else (RESULT_LOSS if player.result == 'loss' else RESULT_TIE)
                room.stats[player.session_id].update_after_round(
                    result_code, player.hand, room.dealer_hand,
                    player.current_bet if room.is_casino else 0
                )
            
            # Send round results
            socketio.emit('multiplayer_round_results', {
                'dealer_value': dealer_final,
                'dealer_busted': dealer_busted,
                'room_state': room.to_dict()
            }, room=room_id)
            
            print(f"[MULTIPLAYER] ========== ROUND {round_num} COMPLETE ==========")
            time.sleep(5.0)  # Give more time to see results (win/loss display)
        
        # ========== GAME FINISHED ==========
        room.game_status = 'finished'
        print(f"[MULTIPLAYER] ========== GAME FINISHED ==========")
        
        # Prepare final stats for all players
        final_stats = {}
        for sid, stats in room.stats.items():
            try:
                # Use MODE_CASINO if room is casino mode, otherwise MODE_MULTIPLAYER
                final_stats[sid] = stats.to_dict(MODE_CASINO if room.is_casino else MODE_MULTIPLAYER)
            except Exception as e:
                print(f"[ERROR] Failed to get stats for {sid}: {e}")
                final_stats[sid] = {
                    'rounds_played': 0,
                    'wins': 0,
                    'losses': 0,
                    'ties': 0,
                    'win_rate': 0,
                    'blackjacks': 0,
                    'busts': 0,
                    'avg_hand': 0
                }
        
        # Determine winner - ROBUST VERSION
        winner_sid = None
        winner_name = 'Unknown'
        winner_character = 'gaya'
        
        try:
            if room.is_casino:
                # Casino: Winner is player with most chips
                if room.players:
                    winner_sid = max(room.players.keys(), key=lambda sid: room.players[sid].chips)
            else:
                # Classic: Winner is player with most wins
                if room.stats:
                    winner_sid = max(room.stats.keys(), key=lambda sid: room.stats[sid].wins)
            
            # Get winner info
            if winner_sid and winner_sid in room.players:
                winner = room.players[winner_sid]
                winner_name = winner.name
                winner_character = winner.character
            elif room.players:
                # Fallback: first player
                winner_sid = list(room.players.keys())[0]
                winner = room.players[winner_sid]
                winner_name = winner.name
                winner_character = winner.character
                
        except Exception as e:
            print(f"[ERROR] Failed to determine winner: {e}")
            # Use first player as fallback
            if room.players:
                winner_sid = list(room.players.keys())[0]
                winner = room.players[winner_sid]
                winner_name = winner.name
                winner_character = winner.character
        
        print(f"[MULTIPLAYER] Winner: {winner_name} (sid: {winner_sid})")
        print(f"[MULTIPLAYER] Final stats: {final_stats}")
        
        # Send game finished event
        finished_data = {
            'stats': final_stats,
            'winner': {
                'id': winner_sid or '',
                'name': winner_name,
                'character': winner_character
            },
            'room_state': room.to_dict()
        }
        
        print(f"[MULTIPLAYER] GAME FINISHED -> emitting finish events to room {room_id}, players={len(room.players)}")
        
        # Broadcast to room as you already do
        socketio.emit('multiplayer_game_finished', finished_data, room=room_id)
        time.sleep(0.2)
        socketio.emit('multiplayer_game_finished', finished_data, room=room_id)
        
        # Backward-compatible finish events (single-player UI likely listens to these)
        socketio.emit('game_finished', {
            'stats': finished_data['stats'],
            'game_mode': MODE_MULTIPLAYER,
            'total_rounds': room.num_rounds,
            'show_stats': True,
            'broke': False,
            'winner': finished_data['winner'],
            'room_state': finished_data['room_state']
        }, room=room_id)
        
        time.sleep(0.2)
        socketio.emit('show_final_stats', finished_data['stats'], room=room_id)
        
        # Fallback: emit directly to each player SID in case their socket is not joined to room_id
        for sid in list(room.players.keys()):
            socketio.emit('multiplayer_game_finished', finished_data, room=sid)
            socketio.emit('game_finished', {
                'stats': finished_data['stats'],
                'game_mode': MODE_MULTIPLAYER,
                'total_rounds': room.num_rounds,
                'show_stats': True,
                'broke': False,
                'winner': finished_data['winner'],
                'room_state': finished_data['room_state']
            }, room=sid)
            socketio.emit('show_final_stats', finished_data['stats'], room=sid)
        
        print(f"[MULTIPLAYER] Game finished event sent!")
        
    except Exception as e:
        print(f"[ERROR] Multiplayer game error: {e}")
        import traceback
        traceback.print_exc()
        socketio.emit('error', {'message': f'Game error: {str(e)}'}, room=room_id)
    finally:
        # Cleanup - ensure all emits are done before closing socket
        # All finish events are emitted above, so safe to close now
        if room and room.tcp_socket:
            try:
                # Don't hold lock while closing - emits already done
                room.tcp_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                room.tcp_socket.close()
            except:
                pass
        print(f"[MULTIPLAYER] Game loop ended for room {room_id}")


@socketio.on('multiplayer_decision')
def handle_multiplayer_decision(data):
    """Handle player decision in multiplayer - FIXED"""
    from flask import request
    session_id = request.sid
    
    if session_id not in player_rooms:
        emit('error', {'message': 'Not in a room'})
        return
    
    room_id = player_rooms[session_id]
    room = game_rooms.get(room_id)
    
    if not room or session_id not in room.players:
        emit('error', {'message': 'Room or player not found'})
        return
    
    player = room.players[session_id]
    current_player = room.get_current_player()
    
    # Only current player can make decisions
    if not current_player or current_player.session_id != session_id:
        emit('error', {'message': 'Not your turn!'})
        return
    
    if player.status != 'playing':
        emit('error', {'message': 'Cannot make decision now'})
        return
    
    decision = data.get('decision')
    print(f"[MULTIPLAYER] {player.name} decision received: {decision}")
    
    # FIX: Only store decision, don't read from TCP here
    # The multiplayer_game_loop will process it and read the card
    if decision in ['Stand', 'Hittt']:
        player.pending_decision = decision
        print(f"[MULTIPLAYER] Stored decision for {player.name}: {decision}")
    else:
        emit('error', {'message': f'Invalid decision: {decision}'})


@socketio.on('multiplayer_place_bet')
def handle_multiplayer_bet(data):
    """Handle bet placement in multiplayer casino mode"""
    from flask import request
    session_id = request.sid
    
    if session_id not in player_rooms:
        emit('error', {'message': 'Not in a room'})
        return
    
    room_id = player_rooms[session_id]
    room = game_rooms.get(room_id)
    
    if not room or session_id not in room.players:
        emit('error', {'message': 'Room or player not found'})
        return
    
    if room.game_status != 'betting':
        emit('error', {'message': 'Not in betting phase'})
        return
    
    player = room.players[session_id]
    bet_amount = data.get('bet', 0)
    
    # Validate bet
    if bet_amount < MIN_BET:
        emit('error', {'message': f'Minimum bet is ${MIN_BET}'})
        return
    
    if bet_amount > player.chips:
        emit('error', {'message': 'Not enough chips!'})
        return
    
    if bet_amount > MAX_BET:
        bet_amount = MAX_BET
    
    # Place the bet
    player.current_bet = bet_amount
    player.chips -= bet_amount
    player.bet_placed = True
    
    print(f"[MULTIPLAYER] {player.name} bet ${bet_amount}, remaining: ${player.chips}")
    
    # Notify all players
    socketio.emit('multiplayer_player_bet', {
        'player_id': session_id,
        'player_name': player.name,
        'bet_amount': bet_amount,
        'remaining_chips': player.chips,
        'room_state': room.to_dict()
    }, room=room_id)
    
    # Check if all players have bet
    all_bet = all(p.bet_placed for p in room.players.values() if p.chips >= MIN_BET)
    if all_bet:
        socketio.emit('multiplayer_all_bets_placed', {
            'room_state': room.to_dict()
        }, room=room_id)


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