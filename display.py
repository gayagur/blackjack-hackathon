"""
Display module for Blackjack Client
All visual output functions in one place for consistency.
"""

from constants import RANKS, SUITS
from game_logic import calculate_hand_value

# Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Box drawing constants
BOX_WIDTH = 60


def strip_ansi(text):
    """Remove ANSI color codes from text for length calculation"""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def print_box(title, content_lines, color=MAGENTA):
    """
    Print content in a nice box.
    
    Args:
        title: Header text (will be centered)
        content_lines: List of strings to display
        color: ANSI color for the box border
    """
    print(f"\n{color}╔{'═' * BOX_WIDTH}╗{RESET}")
    
    if title:
        padded_title = title.center(BOX_WIDTH)
        print(f"{color}║{RESET}{padded_title}{color}║{RESET}")
        print(f"{color}╠{'═' * BOX_WIDTH}╣{RESET}")
    
    print(f"{color}║{RESET}{' ' * BOX_WIDTH}{color}║{RESET}")
    
    for line in content_lines:
        # Remove ANSI codes for length calculation
        clean_line = strip_ansi(line)
        
        # Calculate padding needed
        padding_needed = BOX_WIDTH - len(clean_line)
        if padding_needed < 0:
            padding_needed = 0
        
        left_pad = padding_needed // 2
        right_pad = padding_needed - left_pad
        
        padded_line = " " * left_pad + line + " " * right_pad
        print(f"{color}║{RESET}{padded_line}{color}║{RESET}")
    
    print(f"{color}║{RESET}{' ' * BOX_WIDTH}{color}║{RESET}")
    print(f"{color}╚{'═' * BOX_WIDTH}╝{RESET}\n")


def print_welcome():
    """Print welcome screen with ASCII art"""
    print(f"\n{MAGENTA}")
    print("    ╔══════════════════════════════════════════════════════════╗")
    print("    ║                                                          ║")
    print("    ║     ███████╗██╗      █████╗  ██████╗██╗  ██╗     ██╗ █████╗  ██████╗██╗  ██╗   ║")
    print("    ║     ██╔══██║██║     ██╔══██╗██╔════╝██║ ██╔╝     ██║██╔══██╗██╔════╝██║ ██╔╝   ║")
    print("    ║     ███████║██║     ███████║██║     █████╔╝      ██║███████║██║     █████╔╝    ║")
    print("    ║     ██╔══██║██║     ██╔══██║██║     ██╔═██╗ ██   ██║██╔══██║██║     ██╔═██╗    ║")
    print("    ║     ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗╚█████╔╝██║  ██║╚██████╗██║  ██╗   ║")
    print("    ║     ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝   ║")
    print("    ║                                                          ║")
    print("    ║                  ♠ ♥ ♣ ♦  WELCOME TO THE CASINO  ♦ ♣ ♥ ♠                  ║")
    print("    ║                                                          ║")
    print("    ╚══════════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")


def print_server_menu(servers):
    """
    Print server selection menu.
    
    Args:
        servers: dict of {name: (ip, port)}
    """
    print(f"\n{MAGENTA}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{MAGENTA}║{RESET}{'🎰 AVAILABLE CASINOS 🎰'.center(BOX_WIDTH)}{MAGENTA}║{RESET}")
    print(f"{MAGENTA}╠{'═' * BOX_WIDTH}╣{RESET}")
    print(f"{MAGENTA}║{RESET}{' ' * BOX_WIDTH}{MAGENTA}║{RESET}")
    
    server_list = list(servers.items())
    for i, (name, (ip, port)) in enumerate(server_list, start=1):
        emoji = "🏠" if i == 1 else "🎲" if i == 2 else "🃏"
        line = f"  [{i}] {emoji} {name:<25} {ip}:{port}"
        # Pad to exact width
        clean_line = strip_ansi(line)
        padding = BOX_WIDTH - len(clean_line)
        if padding < 0:
            line = line[:BOX_WIDTH-3] + "..."
            padding = 0
        padded_line = line + " " * padding
        print(f"{MAGENTA}║{RESET}{CYAN}{padded_line}{RESET}{MAGENTA}║{RESET}")
    
    print(f"{MAGENTA}║{RESET}{' ' * BOX_WIDTH}{MAGENTA}║{RESET}")
    
    rescan_line = "  [0] 🔄 Rescan for servers"
    clean_rescan = strip_ansi(rescan_line)
    padding = BOX_WIDTH - len(clean_rescan)
    padded_rescan = rescan_line + " " * padding
    print(f"{MAGENTA}║{RESET}{YELLOW}{padded_rescan}{RESET}{MAGENTA}║{RESET}")
    
    print(f"{MAGENTA}║{RESET}{' ' * BOX_WIDTH}{MAGENTA}║{RESET}")
    print(f"{MAGENTA}╚{'═' * BOX_WIDTH}╝{RESET}\n")


def print_round_header(round_num, total_rounds=None):
    """Print round header"""
    if total_rounds:
        title = f"🎰 ROUND {round_num} of {total_rounds} 🎰"
    else:
        title = f"🎰 ROUND {round_num} 🎰"
    
    print(f"\n{MAGENTA}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{MAGENTA}║{RESET}{title.center(BOX_WIDTH)}{MAGENTA}║{RESET}")
    print(f"{MAGENTA}╚{'═' * BOX_WIDTH}╝{RESET}\n")


def get_card_lines(card):
    """Get the 7 lines for a single card"""
    rank_str = RANKS.get(card.rank, str(card.rank))
    suit_str = SUITS.get(card.suit, '?')
    
    # Color for suit
    if card.suit in (0, 1):  # Heart or Diamond
        suit_color = RED
    else:
        suit_color = RESET
    
    # Handle rank padding
    if len(rank_str) == 2:  # "10"
        top_r = rank_str
        bot_r = rank_str
    else:
        top_r = rank_str + " "
        bot_r = " " + rank_str
    
    return [
        "┌─────────┐",
        f"│ {top_r}      │",
        "│         │",
        f"│    {suit_color}{suit_str}{RESET}    │",
        "│         │",
        f"│      {bot_r} │",
        "└─────────┘"
    ]


def get_hidden_card_lines():
    """Get the 7 lines for a hidden card"""
    return [
        "┌─────────┐",
        "│░░░░░░░░░│",
        "│░░░░░░░░░│",
        "│░░░░░░░░░│",
        "│░░░░░░░░░│",
        "│░░░░░░░░░│",
        "└─────────┘"
    ]


def print_cards_row(cards, hide_indices=None):
    """
    Print cards horizontally.
    
    Args:
        cards: list of Card objects
        hide_indices: list of indices to show as hidden (face-down)
    """
    if not cards:
        return
    
    if hide_indices is None:
        hide_indices = []
    
    # Get all card line arrays
    all_lines = []
    for i, card in enumerate(cards):
        if i in hide_indices:
            all_lines.append(get_hidden_card_lines())
        else:
            all_lines.append(get_card_lines(card))
    
    # Print row by row
    for row in range(7):
        line = "     "
        for card_lines in all_lines:
            line += card_lines[row] + "  "
        print(line)


def print_game_state(player_hand, dealer_hand, hide_dealer_card=True):
    """Print full game state with proper alignment"""
    player_value = calculate_hand_value(player_hand)
    dealer_value = calculate_hand_value(dealer_hand) if dealer_hand else 0
    
    # Dealer section
    print(f"\n{BLUE}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{BLUE}║{RESET}{'DEALER\'S HAND'.center(BOX_WIDTH)}{BLUE}║{RESET}")
    print(f"{BLUE}╠{'═' * BOX_WIDTH}╣{RESET}")
    print(f"{BLUE}║{RESET}{' ' * BOX_WIDTH}{BLUE}║{RESET}")
    
    if dealer_hand and len(dealer_hand) > 0:
        if hide_dealer_card and len(dealer_hand) >= 2:
            # Show first card, hide second card (index 1)
            print_cards_row(dealer_hand, hide_indices=[1])
            visible_value = calculate_hand_value([dealer_hand[0]])
            value_text = f"{BLUE}Value: {visible_value} + ?{RESET}"
            clean_text = f"Value: {visible_value} + ?"
            padding = BOX_WIDTH - len(clean_text) - 4
            left_pad = padding // 2
            right_pad = padding - left_pad
            padded = " " * left_pad + value_text + " " * right_pad
            print(f"{BLUE}║{RESET}{padded}{BLUE}║{RESET}")
        else:
            # Show all cards
            print_cards_row(dealer_hand)
            value_text = f"{BLUE}Value: {dealer_value}{RESET}"
            clean_text = f"Value: {dealer_value}"
            padding = BOX_WIDTH - len(clean_text) - 4
            left_pad = padding // 2
            right_pad = padding - left_pad
            padded = " " * left_pad + value_text + " " * right_pad
            print(f"{BLUE}║{RESET}{padded}{BLUE}║{RESET}")
    else:
        print(f"{BLUE}║{RESET}{' ' * BOX_WIDTH}{BLUE}║{RESET}")
    
    print(f"{BLUE}║{RESET}{' ' * BOX_WIDTH}{BLUE}║{RESET}")
    print(f"{BLUE}╚{'═' * BOX_WIDTH}╝{RESET}")
    
    # Player section
    print(f"\n{GREEN}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{GREEN}║{RESET}{'YOUR HAND'.center(BOX_WIDTH)}{GREEN}║{RESET}")
    print(f"{GREEN}╠{'═' * BOX_WIDTH}╣{RESET}")
    print(f"{GREEN}║{RESET}{' ' * BOX_WIDTH}{GREEN}║{RESET}")
    
    print_cards_row(player_hand)
    value_text = f"{GREEN}Value: {player_value}{RESET}"
    clean_text = f"Value: {player_value}"
    padding = BOX_WIDTH - len(clean_text) - 4
    left_pad = padding // 2
    right_pad = padding - left_pad
    padded = " " * left_pad + value_text + " " * right_pad
    print(f"{GREEN}║{RESET}{padded}{GREEN}║{RESET}")
    
    print(f"{GREEN}║{RESET}{' ' * BOX_WIDTH}{GREEN}║{RESET}")
    print(f"{GREEN}╚{'═' * BOX_WIDTH}╝{RESET}\n")


def print_decision_prompt():
    """Print hit/stand prompt"""
    print(f"\n{CYAN}┌────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  Your move:                            {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}                                        {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}    [H] 👊 HIT   - Draw another card    {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}    [S] 🛑 STAND - Keep your hand       {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}                                        {CYAN}│{RESET}")
    print(f"{CYAN}└────────────────────────────────────────┘{RESET}\n")


def print_result(result, player_value, dealer_value):
    """Print win/lose/tie result"""
    from constants import RESULT_WIN, RESULT_LOSS, RESULT_TIE
    
    if result == RESULT_WIN:
        color = GREEN
        emoji = "🎉"
        text = "Y O U   W I N !"
    elif result == RESULT_LOSS:
        color = RED
        emoji = "😞"
        text = "Y O U   L O S E"
    else:
        color = YELLOW
        emoji = "🤝"
        text = "T I E !"
    
    print(f"\n{color}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{color}║{RESET}{' ' * BOX_WIDTH}{color}║{RESET}")
    result_line = f"{emoji} {emoji} {emoji}  {text}  {emoji} {emoji} {emoji}"
    print(f"{color}║{RESET}{result_line.center(BOX_WIDTH)}{color}║{RESET}")
    print(f"{color}║{RESET}{' ' * BOX_WIDTH}{color}║{RESET}")
    value_line = f"Your hand: {player_value}  |  Dealer: {dealer_value}"
    print(f"{color}║{RESET}{value_line.center(BOX_WIDTH)}{color}║{RESET}")
    print(f"{color}║{RESET}{' ' * BOX_WIDTH}{color}║{RESET}")
    print(f"{color}╚{'═' * BOX_WIDTH}╝{RESET}\n")


def print_bust(value, is_player=True):
    """Print bust message"""
    who = "YOU" if is_player else "DEALER"
    
    print(f"\n{RED}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{RED}║{RESET}{' ' * BOX_WIDTH}{RED}║{RESET}")
    bust_line = f"💥 {who} BUSTED! 💥"
    print(f"{RED}║{RESET}{bust_line.center(BOX_WIDTH)}{RED}║{RESET}")
    value_line = f"Total: {value} (over 21)"
    print(f"{RED}║{RESET}{value_line.center(BOX_WIDTH)}{RED}║{RESET}")
    print(f"{RED}║{RESET}{' ' * BOX_WIDTH}{RED}║{RESET}")
    print(f"{RED}╚{'═' * BOX_WIDTH}╝{RESET}\n")


def print_stats(wins, losses, ties, total_rounds):
    """Print game statistics"""
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


def print_interesting_stats(stats):
    """Print interesting statistics"""
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


def print_message(msg, msg_type="info"):
    """Print a status message with icon"""
    icons = {
        "info": "ℹ️",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "search": "🔍",
        "connect": "🔌",
        "send": "📤",
        "receive": "📥",
        "game": "🎮"
    }
    icon = icons.get(msg_type, "•")
    
    colors = {
        "info": CYAN,
        "success": GREEN,
        "error": RED,
        "warning": YELLOW,
        "search": BLUE,
        "connect": MAGENTA,
        "send": CYAN,
        "receive": CYAN,
        "game": YELLOW
    }
    color = colors.get(msg_type, WHITE)
    
    print(f"{color}[{icon}] {msg}{RESET}")


def print_goodbye():
    """Print goodbye message"""
    print(f"\n{MAGENTA}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{MAGENTA}║{RESET}{' ' * BOX_WIDTH}{MAGENTA}║{RESET}")
    print(f"{MAGENTA}║{RESET}{'👋 Thanks for playing! Goodbye! 👋'.center(BOX_WIDTH)}{MAGENTA}║{RESET}")
    print(f"{MAGENTA}║{RESET}{' ' * BOX_WIDTH}{MAGENTA}║{RESET}")
    print(f"{MAGENTA}╚{'═' * BOX_WIDTH}╝{RESET}\n")

# ============================================================================
# Main Menu Functions
# ============================================================================

def print_main_menu():
    """Print the main game mode selection menu"""
    print(f"""
{MAGENTA}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║         ♠ ♥ ♣ ♦   B L A C K J A C K   ♦ ♣ ♥ ♠                 ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║   {CYAN}Choose Your Game Mode:{RESET}{MAGENTA}                                      ║
║                                                                ║
║   {WHITE}╭─────────────────────────────────────────────────────────╮{MAGENTA}   ║
║   {WHITE}│{RESET}  {GREEN}[1] 🎮 CLASSIC MODE{RESET}                                   {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Simple Blackjack - Hit or Stand                {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Track your wins and losses                     {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Perfect for beginners                          {WHITE}│{MAGENTA}   ║
║   {WHITE}╰─────────────────────────────────────────────────────────╯{MAGENTA}   ║
║                                                                ║
║   {WHITE}╭─────────────────────────────────────────────────────────╮{MAGENTA}   ║
║   {WHITE}│{RESET}  {YELLOW}[2] 🎰 CASINO MODE{RESET}                                    {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Start with 1000 chips                         {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Place bets on each round                      {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Double Down option available                  {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Blackjack (21) pays 1.5x                      {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Go broke = Game Over!                         {WHITE}│{MAGENTA}   ║
║   {WHITE}╰─────────────────────────────────────────────────────────╯{MAGENTA}   ║
║                                                                ║
║   {WHITE}╭─────────────────────────────────────────────────────────╮{MAGENTA}   ║
║   {WHITE}│{RESET}  {CYAN}[3] 🤖 BOT MODE{RESET}                                       {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • AI plays automatically for you                {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Uses mathematically optimal strategy          {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Watch, learn, and enjoy!                      {WHITE}│{MAGENTA}   ║
║   {WHITE}│{RESET}      • Great for testing & statistics                {WHITE}│{MAGENTA}   ║
║   {WHITE}╰─────────────────────────────────────────────────────────╯{MAGENTA}   ║
║                                                                ║
║   {RED}[0] ❌ Exit{RESET}{MAGENTA}                                                  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")


def get_game_mode():
    """Display menu and get user's game mode choice"""
    while True:
        print_main_menu()
        try:
            choice = input(f"{CYAN}  Choose mode (0-3): {RESET}").strip()
            if choice == '0':
                return None
            if choice in ['1', '2', '3']:
                return int(choice)
            print(f"{RED}  Invalid choice! Please enter 0-3{RESET}")
        except (EOFError, KeyboardInterrupt):
            return None


# ============================================================================
# Casino Mode Display Functions
# ============================================================================

def print_chip_balance(chips, bet=None):
    """Display current chip balance with casino style"""
    chip_art = f"""
{YELLOW}    ╔══════════════════════════════════════╗
    ║  💰 CHIP BALANCE                     ║
    ╠══════════════════════════════════════╣
    ║                                      ║
    ║      ╭─────────────────────╮         ║
    ║      │  {WHITE}${chips:,}{YELLOW}              │         ║
    ║      ╰─────────────────────╯         ║
    ║                                      ║"""
    
    if bet:
        chip_art += f"""
    ║      Current Bet: {GREEN}${bet}{YELLOW}              ║
    ║                                      ║"""
    
    chip_art += f"""
    ╚══════════════════════════════════════╝{RESET}
"""
    print(chip_art)


def print_place_bet_prompt(chips, min_bet, max_bet):
    """Display betting prompt with chip stacks"""
    max_allowed = min(max_bet, chips)
    print(f"""
{YELLOW}╔════════════════════════════════════════════════════════════════╗
║                     💵 PLACE YOUR BET 💵                       ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║     {WHITE}Your chips: ${chips:,}{YELLOW}                                        ║
║                                                                ║
║     ╭────────╮  ╭────────╮  ╭────────╮  ╭────────╮            ║
║     │ {RED}♦ $10{YELLOW} │  │ {BLUE}♦ $25{YELLOW} │  │ {GREEN}♦ $50{YELLOW} │  │ {MAGENTA}♦$100{YELLOW} │            ║
║     ╰────────╯  ╰────────╯  ╰────────╯  ╰────────╯            ║
║                                                                ║
║     Min bet: ${min_bet}    Max bet: ${max_allowed}                         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_casino_decision_prompt(can_double_down, current_bet, chips):
    """Display decision options including double down"""
    print(f"""
{CYAN}╔════════════════════════════════════════════════════════════════╗
║                      🎲 YOUR MOVE 🎲                           ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║      {GREEN}[H] 👊 HIT{RESET}{CYAN}      - Draw another card                      ║
║                                                                ║
║      {YELLOW}[S] 🛑 STAND{RESET}{CYAN}    - Keep your hand                        ║
║                                                                ║""")
    
    if can_double_down:
        print(f"""║      {MAGENTA}[D] 💰 DOUBLE{RESET}{CYAN}   - Double bet (${current_bet} → ${current_bet * 2})          ║
║                      Get ONE card, then stand                  ║
║                                                                ║""")
    
    print(f"""╚════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_casino_result(result, player_value, dealer_value, bet, winnings, is_blackjack=False):
    """Display casino-style result with money animation"""
    from constants import RESULT_WIN, RESULT_LOSS, RESULT_TIE
    
    if result == RESULT_WIN:
        if is_blackjack:
            print(f"""
{YELLOW}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║     ♠ ♥ ♣ ♦   B L A C K J A C K !   ♦ ♣ ♥ ♠                   ║
║                                                                ║
║                    🎰 🎰 🎰 WINNER! 🎰 🎰 🎰                    ║
║                                                                ║
║              Your hand: {player_value}  |  Dealer: {dealer_value}                       ║
║                                                                ║
║                  ╭───────────────────────╮                     ║
║                  │  {GREEN}+${winnings:,} CHIPS!{YELLOW}      │                     ║
║                  ╰───────────────────────╯                     ║
║                      (1.5x Blackjack Bonus!)                   ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")
        else:
            print(f"""
{GREEN}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║            🎉 🎉 🎉   Y O U   W I N !   🎉 🎉 🎉               ║
║                                                                ║
║              Your hand: {player_value}  |  Dealer: {dealer_value}                       ║
║                                                                ║
║                  ╭───────────────────────╮                     ║
║                  │     +${winnings:,} CHIPS!      │                     ║
║                  ╰───────────────────────╯                     ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")
    
    elif result == RESULT_LOSS:
        print(f"""
{RED}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║            😞 😞 😞   Y O U   L O S E   😞 😞 😞               ║
║                                                                ║
║              Your hand: {player_value}  |  Dealer: {dealer_value}                       ║
║                                                                ║
║                  ╭───────────────────────╮                     ║
║                  │     -${bet:,} CHIPS       │                     ║
║                  ╰───────────────────────╯                     ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")
    
    else:  # TIE
        print(f"""
{YELLOW}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║               🤝 🤝 🤝   T I E !   🤝 🤝 🤝                    ║
║                                                                ║
║              Your hand: {player_value}  |  Dealer: {dealer_value}                       ║
║                                                                ║
║                  ╭───────────────────────╮                     ║
║                  │    BET RETURNED       │                     ║
║                  ╰───────────────────────╯                     ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_game_over_broke():
    """Display game over screen when player runs out of chips"""
    print(f"""
{RED}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║         ╔═══════════════════════════════════════════╗          ║
║         ║                                           ║          ║
║         ║    💸💸💸 YOU'RE BROKE! 💸💸💸           ║          ║
║         ║                                           ║          ║
║         ╚═══════════════════════════════════════════╝          ║
║                                                                ║
║                                                                ║
║               Your chips have run out...                       ║
║                                                                ║
║         ╭─────────────────────────────────────────╮            ║
║         │                                         │            ║
║         │      🎰 G A M E   O V E R 🎰           │            ║
║         │                                         │            ║
║         │   The house always wins... eventually   │            ║
║         │                                         │            ║
║         ╰─────────────────────────────────────────╯            ║
║                                                                ║
║            Better luck next time, high roller!                 ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_double_down_result(card, new_total):
    """Display the card received after doubling down"""
    print(f"""
{MAGENTA}╔════════════════════════════════════════════════════════════════╗
║                    💰 DOUBLE DOWN! 💰                          ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║                  Bet has been DOUBLED!                         ║
║                                                                ║
║                  You receive ONE card:                         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")
    # Print the card
    if card:
        print_cards_row([card])
    print(f"\n{MAGENTA}                  Final hand value: {new_total}{RESET}\n")


# ============================================================================
# Bot Mode Display Functions
# ============================================================================

def print_bot_header():
    """Display bot mode header"""
    print(f"""
{CYAN}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║           🤖 🤖 🤖  B O T   M O D E  🤖 🤖 🤖                 ║
║                                                                ║
║              Using Optimal Basic Strategy                      ║
║                                                                ║
║         ╭────────────────────────────────────────╮             ║
║         │  The bot will play automatically       │             ║
║         │  using mathematically optimal moves!   │             ║
║         ╰────────────────────────────────────────╯             ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_bot_thinking():
    """Display bot thinking animation"""
    print(f"{CYAN}  🤖 Bot is analyzing...{RESET}")
    import time
    time.sleep(0.5)


def print_bot_decision(decision, player_value, dealer_showing, reason):
    """Display bot's decision with reasoning"""
    decision_text = "HIT 👊" if decision == "Hittt" else "STAND 🛑"
    decision_color = GREEN if decision == "Hittt" else YELLOW
    
    print(f"""
{CYAN}╔════════════════════════════════════════════════════════════════╗
║                    🤖 BOT DECISION 🤖                          ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║      Player's hand value:  {player_value}                                ║
║      Dealer showing:       {dealer_showing}                                ║
║                                                                ║
║      ╭──────────────────────────────────────────╮              ║
║      │                                          │              ║
║      │    Decision:  {decision_color}{decision_text}{CYAN}                     │              ║
║      │                                          │              ║
║      ╰──────────────────────────────────────────╯              ║
║                                                                ║
║      📊 Reason: {reason:<44}║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_bot_stats(stats):
    """Display bot performance statistics"""
    total = stats['wins'] + stats['losses'] + stats['ties']
    win_rate = (stats['wins'] / total * 100) if total > 0 else 0
    
    print(f"""
{CYAN}╔════════════════════════════════════════════════════════════════╗
║                    🤖 BOT PERFORMANCE 🤖                       ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║                  ╭─────────────────────╮                       ║
║                  │ Rounds: {total:<11} │                       ║
║                  ╰─────────────────────╯                       ║
║                                                                ║
║         ✅ Wins:    {stats['wins']:<8}   Win Rate: {win_rate:.1f}%            ║
║         ❌ Losses:  {stats['losses']:<8}                                  ║
║         🤝 Ties:    {stats['ties']:<8}                                  ║
║                                                                ║
║         ──────────────────────────────────────                 ║
║                                                                ║
║         🎯 Correct decisions: Using Basic Strategy             ║
║         📈 Expected house edge: ~0.5%                          ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝{RESET}
""")

def print_cards_row(cards, hide_indices=None):
    """
    Print cards horizontally.
    
    Args:
        cards: list of Card objects
        hide_indices: list of indices to show as hidden (face-down)
    """
    if not cards:
        return
    
    if hide_indices is None:
        hide_indices = []
    
    # Get all card line arrays
    all_lines = []
    for i, card in enumerate(cards):
        if i in hide_indices or card is None:  # Handle None as hidden card
            all_lines.append(get_hidden_card_lines())
        else:
            all_lines.append(get_card_lines(card))
    
    # Print row by row
    for row in range(7):
        line = "     "
        for card_lines in all_lines:
            line += card_lines[row] + "  "
        print(line)


def print_game_state(player_hand, dealer_hand, hide_dealer_card=True):
    """Print full game state with proper alignment"""
    # Filter out None for value calculation
    filtered_player_hand = [c for c in player_hand if c is not None]
    filtered_dealer_hand = [c for c in dealer_hand if c is not None]

    player_value = calculate_hand_value(filtered_player_hand)
    dealer_value = calculate_hand_value(filtered_dealer_hand) if filtered_dealer_hand else 0
    
    # Dealer section
    print(f"\n{BLUE}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{BLUE}║{RESET}{'DEALER\'S HAND'.center(BOX_WIDTH)}{BLUE}║{RESET}")
    print(f"{BLUE}╠{'═' * BOX_WIDTH}╣{RESET}")
    print(f"{BLUE}║{RESET}{' ' * BOX_WIDTH}{BLUE}║{RESET}")
    
    if dealer_hand and len(dealer_hand) > 0:
        if hide_dealer_card and len(dealer_hand) >= 2:
            # Show first card, hide second card (index 1)
            print_cards_row(dealer_hand, hide_indices=[1])
            visible_value = calculate_hand_value([dealer_hand[0]]) if dealer_hand[0] is not None else 0
            value_text = f"{BLUE}Value: {visible_value} + ?{RESET}"
            clean_text = f"Value: {visible_value} + ?"
            padding = BOX_WIDTH - len(clean_text) - 4
            left_pad = padding // 2
            right_pad = padding - left_pad
            padded = " " * left_pad + value_text + " " * right_pad
            print(f"{BLUE}║{RESET}{padded}{BLUE}║{RESET}")
        else:
            # Show all cards
            print_cards_row(dealer_hand)
            value_text = f"{BLUE}Value: {dealer_value}{RESET}"
            clean_text = f"Value: {dealer_value}"
            padding = BOX_WIDTH - len(clean_text) - 4
            left_pad = padding // 2
            right_pad = padding - left_pad
            padded = " " * left_pad + value_text + " " * right_pad
            print(f"{BLUE}║{RESET}{padded}{BLUE}║{RESET}")
    else:
        print(f"{BLUE}║{RESET}{' ' * BOX_WIDTH}{BLUE}║{RESET}")
    
    print(f"{BLUE}║{RESET}{' ' * BOX_WIDTH}{BLUE}║{RESET}")
    print(f"{BLUE}╚{'═' * BOX_WIDTH}╝{RESET}")
    
    # Player section
    print(f"\n{GREEN}╔{'═' * BOX_WIDTH}╗{RESET}")
    print(f"{GREEN}║{RESET}{'YOUR HAND'.center(BOX_WIDTH)}{GREEN}║{RESET}")
    print(f"{GREEN}╠{'═' * BOX_WIDTH}╣{RESET}")
    print(f"{GREEN}║{RESET}{' ' * BOX_WIDTH}{GREEN}║{RESET}")
    
    print_cards_row(player_hand)
    value_text = f"{GREEN}Value: {player_value}{RESET}"
    clean_text = f"Value: {player_value}"
    padding = BOX_WIDTH - len(clean_text) - 4
    left_pad = padding // 2
    right_pad = padding - left_pad
    padded = " " * left_pad + value_text + " " * right_pad
    print(f"{GREEN}║{RESET}{padded}{GREEN}║{RESET}")
    
    print(f"{GREEN}║{RESET}{' ' * BOX_WIDTH}{GREEN}║{RESET}")
    print(f"{GREEN}╚{'═' * BOX_WIDTH}╝{RESET}\n")