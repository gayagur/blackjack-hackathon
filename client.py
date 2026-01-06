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
    MODE_CLASSIC,
    MODE_CASINO,
    MODE_BOT,
    STARTING_CHIPS,
    MIN_BET,
    MAX_BET,
    BLACKJACK_MULTIPLIER,
    DOUBLE_DOWN_ENABLED
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
    get_game_mode,
    print_chip_balance,
    print_place_bet_prompt,
    print_casino_decision_prompt,
    print_casino_result,
    print_game_over_broke,
    print_double_down_result,
    print_bot_header,
    print_bot_thinking,
    print_bot_decision,
    print_bot_stats,
    RED,
    GREEN,
    YELLOW,
    BLUE,
    MAGENTA,
    CYAN,
    WHITE,
    RESET
)


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
        self.current_streak = 0          # Positive = wins, Negative = losses
        self.longest_win_streak = 0
        self.longest_lose_streak = 0
        
        # === HAND STATS (All Modes) ===
        self.total_hand_value = 0        # For calculating average
        self.blackjacks = 0              # 21 with 2 cards
        self.busts = 0                   # Went over 21
        self.biggest_bust = 0            # Highest value over 21
        self.perfect_21s = 0             # Hit exactly 21
        
        # === DECISION STATS (All Modes) ===
        self.total_hits = 0
        self.total_stands = 0
        self.hits_that_busted = 0        # Hits that caused bust
        
        # === DEALER STATS (All Modes) ===
        self.dealer_busts = 0
        self.dealer_blackjacks = 0
        self.times_beat_dealer = 0       # Won by having higher value
        self.times_lost_to_dealer = 0    # Lost by having lower value
        
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
        self.best_chip_balance = 0       # Highest chips ever reached
        self.worst_chip_balance = 0      # Lowest chips ever reached
        
        # === BOT MODE STATS ===
        self.bot_decisions = 0
        self.bot_hits = 0
        self.bot_stands = 0
        self.bot_correct_predictions = 0  # Times bot won when it said "good hand"
        
        # === CARD TRACKING ===
        self.cards_received = []         # All cards received (for analysis)
        self.aces_received = 0
        self.face_cards_received = 0     # J, Q, K
        self.low_cards_received = 0      # 2-6
        self.high_cards_received = 0     # 7-10
    
    def update_after_round(self, result, player_hand, dealer_hand, bet=0, doubled=False):
        """Update all relevant stats after a round"""
        
        # Filter out None values from hands
        filtered_player_hand = [c for c in player_hand if c is not None]
        filtered_dealer_hand = [c for c in dealer_hand if c is not None]
        
        player_value = calculate_hand_value(filtered_player_hand)
        dealer_value = calculate_hand_value(filtered_dealer_hand)
        
        # Basic stats
        self.rounds_played += 1
        self.total_hand_value += player_value
        
        # Track cards
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
        
        # Result tracking
        if result == RESULT_WIN:
            self.wins += 1
            self._update_streak(won=True)
            
            if dealer_value > 21:
                self.dealer_busts += 1
            else:
                self.times_beat_dealer += 1
            
            # Casino tracking
            if bet > 0:
                is_blackjack = len(filtered_player_hand) == 2 and player_value == 21
                if is_blackjack:
                    winnings = int(bet * BLACKJACK_MULTIPLIER)
                else:
                    winnings = bet
                if doubled:
                    winnings = bet * 2  # Double down: bet doubled, win double
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
            
            # Casino tracking
            if bet > 0:
                loss_amount = bet * 2 if doubled else bet
                self.total_lost += loss_amount
                self.biggest_loss = max(self.biggest_loss, loss_amount)
                if doubled:
                    self.double_downs_lost += 1
                    
        else:  # TIE
            self.ties += 1
            self.current_streak = 0
        
        # Special hands
        if player_value == 21:
            if len(filtered_player_hand) == 2:
                self.blackjacks += 1
            else:
                self.perfect_21s += 1
        
        if dealer_value == 21:
            if len(filtered_dealer_hand) == 2:
                self.dealer_blackjacks += 1
        
        # Double down tracking
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
    
    def update_bot_decision(self, decision):
        """Track bot decisions"""
        self.bot_decisions += 1
        if decision == "Hittt":
            self.bot_hits += 1
        else:
            self.bot_stands += 1
    
    def update_chips(self, new_balance):
        """Track chip balance changes"""
        if self.starting_chips == 0:
            self.starting_chips = new_balance
            self.best_chip_balance = new_balance
            self.worst_chip_balance = new_balance
        self.current_chips = new_balance
        self.best_chip_balance = max(self.best_chip_balance, new_balance)
        self.worst_chip_balance = min(self.worst_chip_balance, new_balance)
    
    def print_classic_stats(self):
        """Statistics for Classic Mode"""
        
        win_rate = (self.wins / self.rounds_played * 100) if self.rounds_played > 0 else 0
        avg_hand = (self.total_hand_value / self.rounds_played) if self.rounds_played > 0 else 0
        
        # Current streak display
        if self.current_streak > 0:
            streak_text = f"🔥 {self.current_streak} wins"
            streak_color = GREEN
        elif self.current_streak < 0:
            streak_text = f"📉 {abs(self.current_streak)} losses"
            streak_color = RED
        else:
            streak_text = "None"
            streak_color = WHITE
        
        print(f"""
{CYAN}╔════════════════════════════════════════════════════════════════╗
║                    📊 GAME STATISTICS 📊                       ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║   ┌─────────────────── RESULTS ───────────────────┐            ║
║   │                                               │            ║
║   │   🎮 Rounds Played:     {self.rounds_played:<20}│            ║
║   │   ✅ Wins:              {self.wins:<20}│            ║
║   │   ❌ Losses:            {self.losses:<20}│            ║
║   │   🤝 Ties:              {self.ties:<20}│            ║
║   │   📈 Win Rate:          {win_rate:.1f}%{' ' * 16}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── STREAKS ───────────────────┐            ║
║   │                                               │            ║
║   │   📍 Current Streak:    {streak_color}{streak_text:<20}{CYAN}│            ║
║   │   🔥 Best Win Streak:   {self.longest_win_streak:<20}│            ║
║   │   💀 Worst Lose Streak: {self.longest_lose_streak:<20}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── HANDS ─────────────────────┐            ║
║   │                                               │            ║
║   │   🎰 Blackjacks (21):   {self.blackjacks:<20}│            ║
║   │   🎯 Perfect 21s:       {self.perfect_21s:<20}│            ║
║   │   💥 Busts:             {self.busts:<20}│            ║
║   │   💀 Biggest Bust:      {str(self.biggest_bust) if self.biggest_bust > 0 else 'N/A':<20}│            ║
║   │   📊 Avg Hand Value:    {avg_hand:.1f}{' ' * 16}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── DECISIONS ─────────────────┐            ║
║   │                                               │            ║
║   │   👊 Total Hits:        {self.total_hits:<20}│            ║
║   │   🛑 Total Stands:      {self.total_stands:<20}│            ║
║   │   💥 Hits that Busted:  {self.hits_that_busted:<20}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── DEALER ────────────────────┐            ║
║   │                                               │            ║
║   │   💀 Dealer Busts:      {self.dealer_busts:<20}│            ║
║   │   🎰 Dealer Blackjacks: {self.dealer_blackjacks:<20}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")
    
    def print_casino_stats(self):
        """Statistics for Casino Mode - includes money stats"""
        
        win_rate = (self.wins / self.rounds_played * 100) if self.rounds_played > 0 else 0
        profit = self.total_won - self.total_lost
        profit_sign = "+" if profit >= 0 else ""
        profit_color = GREEN if profit >= 0 else RED
        
        dd_win_rate = (self.double_downs_won / self.double_downs * 100) if self.double_downs > 0 else 0
        
        # ROI calculation
        roi = ((self.current_chips - self.starting_chips) / self.starting_chips * 100) if self.starting_chips > 0 else 0
        roi_sign = "+" if roi >= 0 else ""
        roi_color = GREEN if roi >= 0 else RED
        
        print(f"""
{YELLOW}╔════════════════════════════════════════════════════════════════╗
║                   🎰 CASINO STATISTICS 🎰                      ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║   ┌─────────────────── CHIPS 💰 ──────────────────┐            ║
║   │                                               │            ║
║   │   🏦 Starting Balance:  ${self.starting_chips:<18,}│            ║
║   │   💰 Current Balance:   ${self.current_chips:<18,}│            ║
║   │   📈 Best Balance:      ${self.best_chip_balance:<18,}│            ║
║   │   📉 Worst Balance:     ${self.worst_chip_balance:<18,}│            ║
║   │   {roi_color}📊 ROI:               {roi_sign}{roi:.1f}%{YELLOW}{' ' * 15}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── PROFIT 💵 ─────────────────┐            ║
║   │                                               │            ║
║   │   💵 Total Won:         ${self.total_won:<18,}│            ║
║   │   💸 Total Lost:        ${self.total_lost:<18,}│            ║
║   │   {profit_color}📊 Net Profit:        {profit_sign}${abs(profit):<17,}{YELLOW}│            ║
║   │   🏆 Biggest Win:       ${self.biggest_win:<18,}│            ║
║   │   😢 Biggest Loss:      ${self.biggest_loss:<18,}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── RESULTS 🎲 ────────────────┐            ║
║   │                                               │            ║
║   │   🎮 Rounds Played:     {self.rounds_played:<20}│            ║
║   │   ✅ Wins:              {self.wins:<20}│            ║
║   │   ❌ Losses:            {self.losses:<20}│            ║
║   │   🤝 Ties:              {self.ties:<20}│            ║
║   │   📈 Win Rate:          {win_rate:.1f}%{' ' * 16}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── DOUBLE DOWN 💰 ────────────┐            ║
║   │                                               │            ║
║   │   🎯 Times Doubled:     {self.double_downs:<20}│            ║
║   │   ✅ Doubles Won:       {self.double_downs_won:<20}│            ║
║   │   ❌ Doubles Lost:      {self.double_downs_lost:<20}│            ║
║   │   📈 Double Win Rate:   {dd_win_rate:.1f}%{' ' * 15}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── SPECIAL 🌟 ────────────────┐            ║
║   │                                               │            ║
║   │   🎰 Blackjacks Hit:    {self.blackjacks:<20}│            ║
║   │   💥 Times Busted:      {self.busts:<20}│            ║
║   │   💀 Dealer Busts:      {self.dealer_busts:<20}│            ║
║   │   🔥 Best Win Streak:   {self.longest_win_streak:<20}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")
    
    def print_bot_stats(self):
        """Statistics for Bot Mode - includes AI performance"""
        
        win_rate = (self.wins / self.rounds_played * 100) if self.rounds_played > 0 else 0
        avg_hand = (self.total_hand_value / self.rounds_played) if self.rounds_played > 0 else 0
        bust_rate = (self.busts / self.rounds_played * 100) if self.rounds_played > 0 else 0
        
        hit_ratio = (self.bot_hits / self.bot_decisions * 100) if self.bot_decisions > 0 else 0
        stand_ratio = (self.bot_stands / self.bot_decisions * 100) if self.bot_decisions > 0 else 0
        
        # Expected vs Actual comparison
        expected_win_rate = 42.5  # Theoretical with basic strategy
        performance = win_rate - expected_win_rate
        perf_sign = "+" if performance >= 0 else ""
        perf_color = GREEN if performance >= 0 else RED
        
        print(f"""
{CYAN}╔════════════════════════════════════════════════════════════════╗
║                   🤖 BOT STATISTICS 🤖                         ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║   ┌─────────────────── PERFORMANCE ───────────────┐            ║
║   │                                               │            ║
║   │   🎮 Rounds Played:     {self.rounds_played:<20}│            ║
║   │   ✅ Wins:              {self.wins:<20}│            ║
║   │   ❌ Losses:            {self.losses:<20}│            ║
║   │   🤝 Ties:              {self.ties:<20}│            ║
║   │   📈 Win Rate:          {win_rate:.1f}%{' ' * 16}│            ║
║   │                                               │            ║
║   │   📊 Expected Rate:     {expected_win_rate}% (Basic Strategy)    │            ║
║   │   {perf_color}📈 vs Expected:       {perf_sign}{performance:.1f}%{CYAN}{' ' * 15}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── BOT DECISIONS 🧠 ──────────┐            ║
║   │                                               │            ║
║   │   🧠 Total Decisions:   {self.bot_decisions:<20}│            ║
║   │   👊 Hits Made:         {self.bot_hits:<20}│            ║
║   │   🛑 Stands Made:       {self.bot_stands:<20}│            ║
║   │   📊 Hit Ratio:         {hit_ratio:.1f}%{' ' * 16}│            ║
║   │   📊 Stand Ratio:       {stand_ratio:.1f}%{' ' * 16}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── HAND ANALYSIS 📋 ──────────┐            ║
║   │                                               │            ║
║   │   📊 Avg Hand Value:    {avg_hand:.1f}{' ' * 17}│            ║
║   │   🎰 Blackjacks:        {self.blackjacks:<20}│            ║
║   │   🎯 Perfect 21s:       {self.perfect_21s:<20}│            ║
║   │   💥 Busts:             {self.busts:<20}│            ║
║   │   📉 Bust Rate:         {bust_rate:.1f}%{' ' * 16}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── STREAKS 🔥 ────────────────┐            ║
║   │                                               │            ║
║   │   🔥 Best Win Streak:   {self.longest_win_streak:<20}│            ║
║   │   💀 Worst Lose Streak: {self.longest_lose_streak:<20}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── DEALER 🎩 ─────────────────┐            ║
║   │                                               │            ║
║   │   💀 Dealer Busts:      {self.dealer_busts:<20}│            ║
║   │   🎰 Dealer Blackjacks: {self.dealer_blackjacks:<20}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
║   ┌─────────────────── CARDS ANALYSIS 🃏 ─────────┐            ║
║   │                                               │            ║
║   │   🅰️ Aces Received:      {self.aces_received:<20}│            ║
║   │   👑 Face Cards (J/Q/K): {self.face_cards_received:<20}│            ║
║   │   📈 High Cards (7-10):  {self.high_cards_received:<20}│            ║
║   │   📉 Low Cards (2-6):    {self.low_cards_received:<20}│            ║
║   │                                               │            ║
║   └───────────────────────────────────────────────┘            ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")
    
    def print_mini_stats(self, mode):
        """Print compact stats after each round"""
        win_rate = (self.wins / self.rounds_played * 100) if self.rounds_played > 0 else 0
        
        if mode == MODE_CASINO:
            print(f"""
{YELLOW}┌────────────────────────────────────────┐
│  💰 Chips: ${self.current_chips:,}  |  📊 W/L: {self.wins}/{self.losses}  |  {win_rate:.0f}%  │
└────────────────────────────────────────┘{RESET}
""")
        elif mode == MODE_BOT:
            print(f"""
{CYAN}┌────────────────────────────────────────┐
│  🤖 Round {self.rounds_played}  |  📊 W/L: {self.wins}/{self.losses}  |  {win_rate:.0f}%  │
└────────────────────────────────────────┘{RESET}
""")
        else:
            print(f"""
{GREEN}┌────────────────────────────────────────┐
│  🎮 Round {self.rounds_played}  |  📊 W/L: {self.wins}/{self.losses}  |  {win_rate:.0f}%  │
└────────────────────────────────────────┘{RESET}
""")


# ============================================================================
# Casino Mode Classes
# ============================================================================

class CasinoGame:
    """Manages casino mode game state"""
    
    def __init__(self):
        self.chips = STARTING_CHIPS
        self.current_bet = 0
        self.total_won = 0
        self.total_lost = 0
        self.biggest_win = 0
        self.biggest_loss = 0
        self.blackjacks = 0
        self.double_downs_won = 0
        self.double_downs_lost = 0
    
    def place_bet(self):
        """Get bet amount from player"""
        print_chip_balance(self.chips)
        print_place_bet_prompt(self.chips, MIN_BET, MAX_BET)
        
        while True:
            try:
                bet = int(input(f"{CYAN}  Enter bet amount: ${RESET}").strip())
                if bet < MIN_BET:
                    print(f"{RED}  Minimum bet is ${MIN_BET}{RESET}")
                elif bet > min(MAX_BET, self.chips):
                    print(f"{RED}  Maximum bet is ${min(MAX_BET, self.chips)}{RESET}")
                else:
                    self.current_bet = bet
                    return bet
            except ValueError:
                print(f"{RED}  Please enter a valid number{RESET}")
            except (EOFError, KeyboardInterrupt):
                return None
    
    def can_double_down(self):
        """Check if player can double down"""
        return DOUBLE_DOWN_ENABLED and self.chips >= self.current_bet
    
    def double_down(self):
        """Double the current bet"""
        self.current_bet *= 2
    
    def process_result(self, result, player_hand, dealer_value):
        """Process round result and update chips"""
        player_value = calculate_hand_value(player_hand)
        is_blackjack = len(player_hand) == 2 and player_value == 21
        
        if result == RESULT_WIN:
            if is_blackjack:
                winnings = int(self.current_bet * BLACKJACK_MULTIPLIER)
                self.blackjacks += 1
            else:
                winnings = self.current_bet
            
            self.chips += winnings
            self.total_won += winnings
            self.biggest_win = max(self.biggest_win, winnings)
            
            print_casino_result(result, player_value, dealer_value, 
                              self.current_bet, winnings, is_blackjack)
        
        elif result == RESULT_LOSS:
            self.chips -= self.current_bet
            self.total_lost += self.current_bet
            self.biggest_loss = max(self.biggest_loss, self.current_bet)
            
            print_casino_result(result, player_value, dealer_value,
                              self.current_bet, 0)
        
        else:  # TIE
            print_casino_result(result, player_value, dealer_value,
                              self.current_bet, 0)
        
        self.current_bet = 0
        return self.chips >= MIN_BET  # Return False if broke
    
    def print_casino_stats(self):
        """Print casino-specific statistics"""
        profit = self.total_won - self.total_lost
        profit_color = GREEN if profit >= 0 else RED
        profit_sign = "+" if profit >= 0 else ""
        
        print(f"""
{YELLOW}╔════════════════════════════════════════════════════════════════╗
║                    🎰 CASINO STATISTICS 🎰                     ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║         Final Chip Balance:  ${self.chips:,}                          ║
║         ──────────────────────────────────                     ║
║         💵 Total Won:        ${self.total_won:,}                          ║
║         💸 Total Lost:       ${self.total_lost:,}                          ║
║         {profit_color}📊 Net Profit:       {profit_sign}${profit:,}{YELLOW}                          ║
║         ──────────────────────────────────                     ║
║         🏆 Biggest Win:      ${self.biggest_win:,}                          ║
║         😢 Biggest Loss:     ${self.biggest_loss:,}                          ║
║         🎰 Blackjacks Hit:   {self.blackjacks}                               ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")


# ============================================================================
# Bot Mode Classes
# ============================================================================

class BlackjackBot:
    """
    Bot that plays Blackjack using Basic Strategy.
    Basic Strategy is mathematically optimal for single-deck blackjack.
    """
    
    def __init__(self):
        self.decisions_made = 0
        self.hits = 0
        self.stands = 0
    
    def get_decision(self, player_hand, dealer_showing_card):
        """
        Get optimal decision based on Basic Strategy.
        
        Args:
            player_hand: list of Card objects
            dealer_showing_card: Card object (dealer's visible card)
        
        Returns:
            str: "Hittt" or "Stand"
        """
        player_value = calculate_hand_value(player_hand)
        dealer_value = dealer_showing_card.get_value()
        
        # Count aces in hand (for soft hands)
        has_soft_ace = self._has_soft_ace(player_hand)
        
        print_bot_thinking()
        
        decision, reason = self._basic_strategy(player_value, dealer_value, has_soft_ace)
        
        self.decisions_made += 1
        if decision == "Hittt":
            self.hits += 1
        else:
            self.stands += 1
        
        print_bot_decision(decision, player_value, dealer_value, reason)
        
        return decision
    
    def _has_soft_ace(self, hand):
        """Check if hand has a soft ace (ace counted as 11)"""
        total = calculate_hand_value(hand)
        aces = sum(1 for card in hand if card.rank == 1)
        
        # If we have an ace and haven't busted, it's soft
        return aces > 0 and total <= 21
    
    def _basic_strategy(self, player_value, dealer_value, is_soft):
        """
        Implement Basic Strategy.
        Returns (decision, reason)
        """
        
        # Always stand on 21
        if player_value == 21:
            return ("Stand", "21 is perfect - always stand!")
        
        # Always hit on 8 or less
        if player_value <= 8:
            return ("Hittt", "Low hand - always hit on 8 or less")
        
        # Soft hands (with ace counted as 11)
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
        
        # Hard hands
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
            if dealer_value <= 9:
                return ("Hittt", "10 vs dealer 2-9 - hit")
            else:
                return ("Hittt", "10 vs dealer 10+ - hit carefully")
        
        elif player_value == 9:
            if 3 <= dealer_value <= 6:
                return ("Hittt", "9 vs dealer 3-6 - hit")
            else:
                return ("Hittt", "9 vs dealer 2 or 7+ - hit")
        
        # Default hit for anything else
        return ("Hittt", "Basic strategy says hit")


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


def get_user_decision(casino_game=None) -> str:
    """
    Ask user for hit/stand/double down, return 'Hittt', 'Stand', or 'DoubleDown'.
    
    Args:
        casino_game: CasinoGame instance if in casino mode, None otherwise
    
    Returns:
        str: "Hittt", "Stand", or "DoubleDown"
    """
    while True:
        try:
            if casino_game:
                can_double = casino_game.can_double_down()
                print_casino_decision_prompt(can_double, casino_game.current_bet, casino_game.chips)
                choice = input(f"{CYAN}Choice (h/s/d): {RESET}").strip().lower()
                if choice == 'h' or choice == 'hit':
                    return "Hittt"
                elif choice == 's' or choice == 'stand':
                    return "Stand"
                elif (choice == 'd' or choice == 'double') and can_double:
                    return "DoubleDown"
                else:
                    print(f"{YELLOW}Please enter 'h' for Hit, 's' for Stand, or 'd' for Double Down{RESET}")
            else:
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




def play_round(tcp_socket: socket.socket, round_num: int, total_rounds: int = 1, game_stats=None, casino_game=None, bot=None, game_mode=MODE_CLASSIC) -> tuple:
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
    
    # Check for blackjack (21 with 2 cards) - will be tracked in update_after_round
    # if len(my_hand) == 2 and calculate_hand_value(my_hand) == 21:
    #     if game_stats is not None:
    #         game_stats.blackjacks += 1
    
    while True:
        # Check if already bust (shouldn't happen, but just in case)
        if is_bust(my_hand):
            my_value = calculate_hand_value(my_hand)
            player_bust = True
            # Track biggest bust - will be tracked in update_after_round
            print_bust(my_value, is_player=True)
            
            # Process result for casino mode
            if casino_game:
                dealer_showing_value = calculate_hand_value([dealer_hand[0]]) if dealer_hand and dealer_hand[0] else 0
                still_playing = casino_game.process_result(RESULT_LOSS, my_hand, dealer_showing_value)
                if not still_playing:
                    print_game_over_broke()
            else:
                print_result(RESULT_LOSS, my_value, 0)
            
            return (RESULT_LOSS, hits_this_round, stands_this_round, my_value, my_hand, dealer_hand)
        
        # Get user decision (from bot, casino mode, or user)
        if bot:
            decision = bot.get_decision(my_hand, dealer_hand[0])
            time.sleep(1)  # Small delay for viewing
        else:
            decision = get_user_decision(casino_game)
        
        # Handle double down
        if decision == "DoubleDown" and casino_game:
            casino_game.double_down()
            print_double_down_result(None, calculate_hand_value(my_hand))  # Will update after receiving card
            send_decision(tcp_socket, "Hittt")
            # Receive one card
            result, card = receive_card(tcp_socket)
            my_hand.append(card)
            time.sleep(0.3)
            print_double_down_result(card, calculate_hand_value(my_hand))
            print_game_state(my_hand, dealer_hand, hide_dealer_card=True)
            # After double down, automatically stand
            decision = "Stand"
            send_decision(tcp_socket, "Stand")
        else:
            # Send decision to server
            send_decision(tcp_socket, decision)
        
        if decision == "Hittt":
            hits_this_round += 1
            # Update bot decision stats if bot mode
            if bot and game_stats:
                game_stats.update_bot_decision("Hittt")
            
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
                # Track bust in stats
                if game_stats:
                    game_stats.busts += 1
                    game_stats.biggest_bust = max(game_stats.biggest_bust, my_value)
                    game_stats.update_decision("Hittt", caused_bust=True)
                print_bust(my_value, is_player=True)
                
                # Process result for casino mode
                if casino_game:
                    dealer_showing_value = calculate_hand_value([dealer_hand[0]]) if dealer_hand and dealer_hand[0] else 0
                    still_playing = casino_game.process_result(result, my_hand, dealer_showing_value)
                    if not still_playing:
                        print_game_over_broke()
                else:
                    print_result(result, my_value, 0)
                
                return (result, hits_this_round, stands_this_round, my_value, my_hand, dealer_hand)
        
        elif decision == "Stand":
            stands_this_round += 1
            # Update bot decision stats if bot mode
            if bot and game_stats:
                game_stats.update_bot_decision("Stand")
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
    
    # Track dealer busts - will be tracked in update_after_round
    # if dealer_bust and game_stats is not None:
    #     game_stats.dealer_busts += 1
    
    # Final display - show all cards
    print_game_state(my_hand, dealer_hand, hide_dealer_card=False)
    
    # Determine final result
    final_result = RESULT_WIN if dealer_bust else result
    
    # Process result for casino mode (updates chips and displays result)
    if casino_game:
        still_playing = casino_game.process_result(final_result, my_hand, dealer_value)
        if not still_playing:
            print_game_over_broke()
    else:
        # Show result screen for classic mode
        if dealer_bust:
            print_bust(dealer_value, is_player=False)
        print_result(final_result, my_value, dealer_value)
    
    return (final_result, hits_this_round, stands_this_round, my_value, my_hand, dealer_hand)


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
        stats = GameStatistics()
        
        # Play all rounds
        for round_num in range(1, num_rounds + 1):
            try:
                result, hits, stands, hand_value, my_hand, dealer_hand = play_round(tcp_socket, round_num, num_rounds, stats, None, None, MODE_CLASSIC)
                
                # Update statistics after round
                bet = 0
                doubled = False
                stats.update_after_round(result, my_hand, dealer_hand, bet, doubled)
                
                # Update decision stats
                for _ in range(hits):
                    stats.update_decision("Hittt", False)
                for _ in range(stands):
                    stats.update_decision("Stand", False)
                
                # Print mini stats after each round
                stats.print_mini_stats(MODE_CLASSIC)
                
            except Exception as e:
                print_message(f"Round {round_num} failed: {e}", "error")
                break
        
        # Print full statistics
        stats.print_classic_stats()
        
        return stats
    
    except socket.timeout:
        print_message("Connection timeout", "error")
        return GameStatistics()
    except Exception as e:
        print_message(f"Connection error: {e}", "error")
        return GameStatistics()
    finally:
        if tcp_socket:
            try:
                tcp_socket.close()
                print_message("Connection closed", "connect")
            except:
                pass


def play_casino_mode(server_ip, tcp_port, num_rounds, casino_game):
    """Play casino mode with betting"""
    tcp_socket = None
    try:
        # Connect to server
        print_message("Connecting to server...", "connect")
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(30.0)
        tcp_socket.connect((server_ip, tcp_port))
        print_message("Connected successfully!", "success")
        
        # Send request
        request_packet = create_request_packet(num_rounds, TEAM_NAME)
        tcp_socket.sendall(request_packet)
        print_message(f"Requesting {num_rounds} rounds...", "send")
        print_message("Game starting!", "game")
        
        # Initialize statistics
        stats = GameStatistics()
        stats.update_chips(casino_game.chips)
        
        # Play rounds
        for round_num in range(1, num_rounds + 1):
            # Place bet before each round
            bet = casino_game.place_bet()
            if bet is None:
                break
            
            try:
                result, hits, stands, hand_value, my_hand, dealer_hand = play_round(tcp_socket, round_num, num_rounds, stats, casino_game, None, MODE_CASINO)
                
                # Update statistics after round
                doubled = (casino_game.current_bet == bet * 2) if bet > 0 else False
                stats.update_after_round(result, my_hand, dealer_hand, bet, doubled)
                
                # Update decision stats
                for _ in range(hits):
                    stats.update_decision("Hittt", False)
                for _ in range(stands):
                    stats.update_decision("Stand", False)
                
                # Update chips
                stats.update_chips(casino_game.chips)
                
                # Print mini stats after each round
                stats.print_mini_stats(MODE_CASINO)
                
                # Check if broke (for casino mode)
                if casino_game and casino_game.chips < MIN_BET:
                    break
                    
            except Exception as e:
                print_message(f"Round {round_num} failed: {e}", "error")
                break
        
        # Print full statistics
        stats.print_casino_stats()
        
        return stats
        
    except Exception as e:
        print_message(f"Connection error: {e}", "error")
        return GameStatistics()
    finally:
        if tcp_socket:
            try:
                tcp_socket.close()
            except:
                pass


def play_bot_mode(server_ip, tcp_port, num_rounds, bot):
    """Play bot mode with AI"""
    tcp_socket = None
    try:
        # Connect to server
        print_message("Connecting to server...", "connect")
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(30.0)
        tcp_socket.connect((server_ip, tcp_port))
        print_message("Connected successfully!", "success")
        
        # Send request
        request_packet = create_request_packet(num_rounds, TEAM_NAME)
        tcp_socket.sendall(request_packet)
        print_message(f"Requesting {num_rounds} rounds...", "send")
        print_message("Bot starting to play!", "game")
        
        # Initialize statistics
        stats = GameStatistics()
        
        # Play rounds
        for round_num in range(1, num_rounds + 1):
            try:
                result, hits, stands, hand_value, my_hand, dealer_hand = play_round(tcp_socket, round_num, num_rounds, stats, None, bot, MODE_BOT)
                
                # Update statistics after round
                bet = 0
                doubled = False
                stats.update_after_round(result, my_hand, dealer_hand, bet, doubled)
                
                # Update decision stats
                for _ in range(hits):
                    stats.update_bot_decision("Hittt")
                for _ in range(stands):
                    stats.update_bot_decision("Stand")
                
                # Print mini stats after each round
                stats.print_mini_stats(MODE_BOT)
                    
            except Exception as e:
                print_message(f"Round {round_num} failed: {e}", "error")
                break
        
        # Print full statistics
        stats.print_bot_stats()
        
        return stats
        
    except Exception as e:
        print_message(f"Connection error: {e}", "error")
        return GameStatistics()
    finally:
        if tcp_socket:
            try:
                tcp_socket.close()
            except:
                pass


def main():
    """Main client entry point with game mode selection"""
    
    # Show welcome
    print_welcome()
    
    # Get game mode
    game_mode = get_game_mode()
    if game_mode is None:
        print_goodbye()
        return
    
    # Initialize mode-specific objects
    casino_game = None
    bot = None
    
    if game_mode == MODE_CASINO:
        casino_game = CasinoGame()
        print(f"\n{YELLOW}  🎰 CASINO MODE - Starting with ${STARTING_CHIPS} chips!{RESET}\n")
    elif game_mode == MODE_BOT:
        bot = BlackjackBot()
        print_bot_header()
    else:
        print(f"\n{GREEN}  🎮 CLASSIC MODE - Let's play!{RESET}\n")
    
    # Main game loop
    try:
        while True:
            # Get number of rounds (not for bot mode with auto-play)
            if game_mode == MODE_BOT:
                try:
                    num_rounds_input = input(f"\n{CYAN}How many rounds for the bot? {RESET}").strip()
                    num_rounds = int(num_rounds_input)
                    if num_rounds < 1 or num_rounds > 255:
                        print(f"{YELLOW}Please enter a number between 1 and 255{RESET}")
                        continue
                except ValueError:
                    print(f"{YELLOW}Please enter a valid number{RESET}")
                    continue
                except (EOFError, KeyboardInterrupt):
                    break
            else:
                try:
                    num_rounds_input = input(f"\n{CYAN}How many rounds? {RESET}").strip()
                    num_rounds = int(num_rounds_input)
                    if num_rounds < 1 or num_rounds > 255:
                        print(f"{YELLOW}Please enter a number between 1 and 255{RESET}")
                        continue
                except ValueError:
                    print(f"{YELLOW}Please enter a valid number{RESET}")
                    continue
                except (EOFError, KeyboardInterrupt):
                    break
            
            # Server selection
            try:
                server_info = listen_for_offers()
                if server_info is None:
                    continue
                server_ip, tcp_port, server_name = server_info
            except KeyboardInterrupt:
                break
            
            # Play game based on mode
            if game_mode == MODE_CASINO:
                stats = play_casino_mode(server_ip, tcp_port, num_rounds, casino_game)
                if casino_game.chips < MIN_BET:
                    print_game_over_broke()
                    break
            elif game_mode == MODE_BOT:
                stats = play_bot_mode(server_ip, tcp_port, num_rounds, bot)
            else:
                stats = play_game(server_ip, tcp_port, num_rounds)
            
            # Ask to play again
            try:
                again = input(f"\n{CYAN}Play again? (y/n): {RESET}").strip().lower()
                if again != 'y':
                    break
            except (EOFError, KeyboardInterrupt):
                break
        
        # Stats are already printed inside play_game, play_casino_mode, and play_bot_mode
        print_goodbye()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Thanks for playing!{RESET}")
    except Exception as e:
        print_message(f"FATAL ERROR: {e}", "error")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

