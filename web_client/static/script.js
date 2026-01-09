// ============================================
// PROFESSIONAL BLACKJACK WEB CLIENT
// ============================================

// Socket.IO connection
const socket = io();
let selectedServer = null;
let gameState = null;
let currentRound = 0;
let totalRounds = 0;
let selectedGameMode = null;
let selectedCharacter = null;
let currentChips = 1000;
let waitingForBet = false;
let currentBet = 0;
let playerChips = 1000;
let minBet = 10;
let maxBet = 1000;
let gameInProgress = false;
let playerWins = 0;
let dealerWins = 0;
let bannerTimer = null; // Timer for auto-hiding result banner

// ============================================
// SOCKET EVENT HANDLERS
// ============================================

socket.on('connect', (data) => {
    console.log('Connected to web server');
    showMessage('Connected to server', 'success');
});

socket.on('connected_to_game', (data) => {
    console.log('[SOCKET connected_to_game]', data);
    showMessage('Connected to game!', 'success');
    totalRounds = data.rounds;
    selectedGameMode = data.game_mode;
    gameInProgress = true;
    
    // Reset score for new game
    playerWins = 0;
    dealerWins = 0;
    updateLiveScore(); // Show initial score
    
    // Update character displays
    if (selectedCharacter) {
        const playerImg = document.getElementById('player-character-img');
        const playerName = document.getElementById('player-character-name');
        if (playerImg) {
            playerImg.src = `/assests/${selectedCharacter}.png`;
            playerImg.alt = selectedCharacter.toUpperCase();
        }
        if (playerName) {
            playerName.textContent = `YOU - ${selectedCharacter.toUpperCase()}`;
        }
    }
    
    // Ensure dealer character is visible
    const dealerImg = document.getElementById('dealer-character-img');
    if (dealerImg) {
        dealerImg.src = '/assests/yossi.png';
        dealerImg.alt = 'YOSSI';
    }
    
    if (selectedGameMode === 2) { // Casino Mode
        document.getElementById('betting-panel').style.display = 'block';
    } else {
        document.getElementById('betting-panel').style.display = 'none';
    }
    
    if (selectedGameMode === 3) { // Bot Mode
        document.getElementById('bot-decision').style.display = 'block';
    } else {
        document.getElementById('bot-decision').style.display = 'none';
    }
});

socket.on('servers_found', (data) => {
    const servers = data.servers;
    const list = document.getElementById('servers-list');
    list.innerHTML = '';
    
    if (Object.keys(servers).length === 0) {
        list.innerHTML = '<div class="status-message" style="color: #ff6b6b;">No servers found. Make sure the server is running.</div>';
        return;
    }
    
    Object.entries(servers).forEach(([name, [ip, port]], index) => {
        const item = document.createElement('div');
        item.className = 'server-item';
        item.innerHTML = `
            <div>
                <strong>${name}</strong>
                <div>${ip}:${port}</div>
            </div>
            <button class="connect-button" onclick="selectServer('${name}', '${ip}', ${port})">SELECT</button>
        `;
        list.appendChild(item);
        
        // Stagger animation
        setTimeout(() => {
            item.style.opacity = '0';
            item.style.transform = 'translateX(-20px)';
            item.style.transition = 'all 0.5s';
            setTimeout(() => {
                item.style.opacity = '1';
                item.style.transform = 'translateX(0)';
            }, 50);
        }, index * 100);
    });
    
    showMessage(`Found ${Object.keys(servers).length} server(s)`, 'success');
});

socket.on('round_start', (data) => {
    console.log('[SOCKET round_start]', data);
    currentRound = data.round;
    totalRounds = data.total;
    
    // Make sure we're on the game screen
    showScreen('game-screen');
    
    // Hide result banner (in case it's still showing)
    hideRoundBanner();
    
    // Update live score (should already be visible)
    updateLiveScore();
    
    const header = document.getElementById('round-header');
    if (header) {
        header.innerHTML = `<div>🎰 ROUND ${data.round} OF ${data.total} 🎰</div>`;
        header.style.animation = 'none';
        setTimeout(() => {
            header.style.animation = 'screenFadeIn 0.6s ease-out';
        }, 10);
    }
    
    // Clear previous round
    const playerHand = document.getElementById('player-hand');
    const dealerHand = document.getElementById('dealer-hand');
    const gameMessage = document.getElementById('game-message');
    const controls = document.getElementById('controls');
    const bettingPanel = document.getElementById('betting-panel');
    
    if (playerHand) playerHand.innerHTML = '';
    if (dealerHand) dealerHand.innerHTML = '';
    if (gameMessage) {
        gameMessage.innerHTML = '';
        gameMessage.className = 'game-message';
    }
    if (controls) controls.style.display = 'none';
    if (bettingPanel) bettingPanel.style.display = 'none';
    
    // Hide result overlay if showing
    const resultScreen = document.getElementById('result-screen');
    if (resultScreen && resultScreen.classList.contains('active')) {
        resultScreen.classList.remove('active');
    }
    
    // Reset values
    const playerValue = document.getElementById('player-value');
    const dealerValue = document.getElementById('dealer-value');
    if (playerValue) playerValue.textContent = '';
    if (dealerValue) dealerValue.textContent = '';
});

socket.on('game_state', (data) => {
    gameState = data;
    updateGameDisplay();
    
    if (data.is_blackjack) {
        // Will be handled by blackjack event
    }
});

socket.on('blackjack', () => {
    showMessage('🎰 BLACKJACK! 🎰', 'success');
    createConfetti(50);
    playSound('win');
});

socket.on('card_received', (data) => {
    console.log('[SOCKET card_received]', data);
    if (data.type === 'player') {
        addCard('player-hand', data.rank, data.suit, true);
    } else if (data.type === 'dealer') {
        if (data.hidden) {
            addHiddenCard('dealer-hand');
        } else {
            addCard('dealer-hand', data.rank, data.suit, false);
        }
    }
    updateGameDisplay();
});

socket.on('reveal_hidden_card', (data) => {
    const dealerHand = document.getElementById('dealer-hand');
    const hiddenCard = dealerHand.querySelector('.card.hidden');
    if (hiddenCard) {
        hiddenCard.classList.remove('hidden');
        hiddenCard.classList.add('reveal');
        setTimeout(() => {
            hiddenCard.innerHTML = getCardHTML(data.rank, data.suit);
        }, 400);
    }
    updateGameDisplay();
});

socket.on('place_bet', (data) => {
    console.log('[SOCKET place_bet]', data);
    waitingForBet = true;
    currentChips = data.chips;
    playerChips = data.chips;
    minBet = data.min_bet || 10;
    maxBet = data.max_bet || 1000;
    currentBet = minBet;
    
    // Update slider limits
    const slider = document.getElementById('bet-slider');
    if (slider) {
        slider.min = minBet;
        slider.max = Math.min(maxBet, playerChips);
        slider.value = minBet;
    }
    
    const maxBetLabel = document.getElementById('max-bet-label');
    if (maxBetLabel) {
        maxBetLabel.textContent = '$' + Math.min(maxBet, playerChips).toLocaleString();
    }
    
    // Update visuals
    updateBalanceChips(playerChips);
    updateBetChips(currentBet);
    updateChipButtons();
    
    // Show betting panel
    const bettingPanel = document.getElementById('betting-panel');
    if (bettingPanel) {
        bettingPanel.style.display = 'block';
    }
    
    // Hide controls
    const controls = document.getElementById('controls');
    if (controls) {
        controls.style.display = 'none';
    }
    
    showMessage('Place your bet!', 'info');
});

socket.on('your_turn', (data) => {
    document.getElementById('controls').style.display = 'flex';
    showMessage('🎲 YOUR TURN - Make your decision!', 'info');
    enableButtons();
    
    // Show double down button if available
    if (data && data.can_double) {
        document.getElementById('double-btn').style.display = 'flex';
    } else {
        document.getElementById('double-btn').style.display = 'none';
    }
    
    // Animate buttons
    const buttons = document.querySelectorAll('.control-button');
    buttons.forEach((btn, index) => {
        setTimeout(() => {
            btn.style.animation = 'none';
            setTimeout(() => {
                btn.style.animation = 'screenFadeIn 0.5s ease-out';
            }, 10);
        }, index * 100);
    });
});

socket.on('bot_decision', (data) => {
    document.getElementById('bot-reason').textContent = data.reason;
    showMessage(`🤖 Bot decides: ${data.decision} - ${data.reason}`, 'info');
});

socket.on('dealer_turn', () => {
    document.getElementById('controls').style.display = 'none';
    showMessage('🎩 DEALER\'S TURN...', 'info');
    disableButtons();
});

socket.on('bust', (data) => {
    showMessage(`💥 BUST! You went over 21!`, 'error');
    const playerValue = document.getElementById('player-value');
    playerValue.classList.add('bust');
    playSound('bust');
    createShakeEffect(document.getElementById('player-hand'));
});

socket.on('round_over', (data) => {
    console.log('[SOCKET round_over]', data);
    disableButtons();
    document.getElementById('controls').style.display = 'none';
    
    // Update score
    if (data.result === 'win') {
        playerWins++;
    } else if (data.result === 'loss') {
        dealerWins++;
    }
    // Ties don't count for either side
    
    // Show round result banner with score
    showRoundResultBanner(data);
});

socket.on('game_finished', (data) => {
    console.log('[SOCKET game_finished]', data);
    console.log('[DEBUG] game_finished - game_mode:', data.game_mode, 'stats.mode:', data.stats?.mode);
    // Mark game as finished
    gameInProgress = false;
    // Use game_mode from data, or stats.mode, or selectedGameMode as fallback
    const mode = data.game_mode || data.stats?.mode || selectedGameMode;
    console.log('[DEBUG] Using mode for final stats:', mode);
    // Show final statistics
    showFinalStats(data.stats, mode, data.broke);
});

socket.on('show_final_stats', (stats) => {
    console.log('[SOCKET show_final_stats]', stats);
    console.log('[DEBUG] show_final_stats - stats.mode:', stats.mode, 'selectedGameMode:', selectedGameMode);
    gameInProgress = false;
    // Use stats.mode if available, otherwise try to get from selectedGameMode
    const mode = stats.mode || selectedGameMode;
    console.log('[DEBUG] Using mode for final stats:', mode);
    showFinalStats(stats, mode, false);
});

socket.on('game_over_broke', (data) => {
    console.log('[SOCKET game_over_broke]', data);
    gameInProgress = false;
    showMessage(`💸 GAME OVER! You ran out of chips! ($${data.chips})`, 'error');
    // The backend will send game_finished event next with broke=true
});

socket.on('next_round', (data) => {
    console.log('[SOCKET next_round]', data);
    showMessage(`Round ${data.current} complete! Starting round ${data.next}...`, 'info');
    // The server will emit 'round_start' next, which will handle the transition
});

socket.on('mini_stats', (data) => {
    // Update mini stats display if needed
    console.log('Mini stats:', data);
});

socket.on('error', (data) => {
    showMessage(`Error: ${data.message}`, 'error');
    console.error('Error:', data);
});

socket.on('decision_made', (data) => {
    showMessage('Decision sent...', 'info');
});

// ============================================
// UI FUNCTIONS
// ============================================

function showScreen(screenId) {
    console.log('[DEBUG] showScreen called with:', screenId);
    try {
        // Hide all screens
        const allScreens = document.querySelectorAll('.screen');
        if (allScreens.length === 0) {
            console.error('[ERROR] No screens found in DOM');
            return;
        }
        allScreens.forEach(s => {
            s.classList.remove('active');
        });
        
        // Show the requested screen
        const targetScreen = document.getElementById(screenId);
        if (!targetScreen) {
            console.error('[ERROR] Screen not found:', screenId);
            return;
        }
        targetScreen.classList.add('active');
        console.log('[DEBUG] Screen activated:', screenId);
    } catch (error) {
        console.error('[ERROR] Failed to show screen:', screenId, error);
    }
}

function showGameModeSelection() {
    console.log('[DEBUG] showGameModeSelection called');
    try {
        const screen = document.getElementById('game-mode-screen');
        if (!screen) {
            console.error('[ERROR] game-mode-screen not found in DOM');
            alert('Error: Game mode screen not found. Please refresh the page.');
            return;
        }
        showScreen('game-mode-screen');
        console.log('[DEBUG] Successfully switched to game mode selection');
    } catch (error) {
        console.error('[ERROR] Failed to show game mode selection:', error);
        alert('Error: Could not load game mode selection. Please refresh the page.');
    }
}

function selectGameMode(mode) {
    selectedGameMode = mode;
    showScreen('character-screen');
}

function selectCharacter(character) {
    selectedCharacter = character;
    document.querySelectorAll('.character-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
    
    // Update player character display
    const playerImg = document.getElementById('player-character-img');
    const playerName = document.getElementById('player-character-name');
    if (playerImg) {
        playerImg.src = `/assests/${character}.png`;
        playerImg.alt = character.toUpperCase();
    }
    if (playerName) {
        playerName.textContent = `YOU - ${character.toUpperCase()}`;
    }
    
    setTimeout(() => {
        showScreen('server-screen');
        scanServers();
    }, 500);
}

function showServerSelection() {
    showScreen('server-screen');
    scanServers();
}

function scanServers() {
    showMessage('Scanning for servers...', 'info');
    socket.emit('scan_servers');
}

function selectServer(name, ip, port) {
    selectedServer = {name, ip, port};
    document.getElementById('rounds-input').style.display = 'block';
    showMessage(`Selected: ${name}`, 'success');
    
    // Highlight selected server
    document.querySelectorAll('.server-item').forEach(item => {
        item.style.borderColor = 'rgba(255, 215, 0, 0.2)';
        if (item.textContent.includes(name)) {
            item.style.borderColor = 'var(--casino-gold)';
            item.style.boxShadow = '0 5px 20px rgba(255, 215, 0, 0.5)';
        }
    });
}

function connectToServer() {
    if (!selectedServer) {
        showMessage('Please select a server first', 'error');
        return;
    }
    
    if (!selectedGameMode) {
        showMessage('Please select a game mode first', 'error');
        return;
    }
    
    if (!selectedCharacter) {
        showMessage('Please select a character first', 'error');
        return;
    }
    
    const rounds = parseInt(document.getElementById('num-rounds').value) || 1;
    if (rounds < 1 || rounds > 255) {
        showMessage('Number of rounds must be between 1 and 255', 'error');
        return;
    }
    
    socket.emit('connect_to_server', {
        ip: selectedServer.ip,
        port: selectedServer.port,
        rounds: rounds,
        game_mode: selectedGameMode,
        player_character: selectedCharacter
    });
    
    showScreen('game-screen');
    showMessage('Connecting to server...', 'info');
}

// ==================== 
// BETTING VARIABLES
// ====================
// (Already defined at top of file)

// ====================
// CHIP VISUALIZATION
// ====================

function updateBalanceChips(balance) {
    const container = document.getElementById('balance-chips');
    if (!container) return;
    
    container.innerHTML = '';
    
    const chipTypes = [
        { value: 500, class: 'chip-purple', label: '$500' },
        { value: 100, class: 'chip-gold', label: '$100' },
        { value: 50, class: 'chip-green', label: '$50' },
        { value: 25, class: 'chip-blue', label: '$25' },
        { value: 10, class: 'chip-red', label: '$10' }
    ];
    
    let remaining = balance;
    
    chipTypes.forEach(chipType => {
        const count = Math.floor(remaining / chipType.value);
        remaining = remaining % chipType.value;
        
        if (count > 0) {
            const stack = document.createElement('div');
            stack.className = 'chip-stack';
            
            // Show max 5 chips per stack visually
            const visualCount = Math.min(count, 5);
            
            for (let i = 0; i < visualCount; i++) {
                const chip = document.createElement('div');
                chip.className = `chip ${chipType.class}`;
                chip.textContent = chipType.label;
                chip.style.animationDelay = (i * 0.05) + 's';
                stack.appendChild(chip);
            }
            
            // Show count if more than 5
            if (count > 5) {
                const countBadge = document.createElement('div');
                countBadge.className = 'chip-stack-count';
                countBadge.textContent = 'x' + count;
                stack.appendChild(countBadge);
            }
            
            container.appendChild(stack);
        }
    });
    
    // Update balance text
    const balanceText = document.getElementById('chip-balance');
    if (balanceText) {
        balanceText.textContent = '$' + balance.toLocaleString();
    }
}

function updateBetChips(betAmount) {
    const container = document.getElementById('bet-chips');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (betAmount === 0) {
        container.innerHTML = '<div class="empty-bet">Click chips to bet</div>';
        const betTotal = document.getElementById('bet-total');
        if (betTotal) betTotal.textContent = '$0';
        const btnAmount = document.getElementById('btn-bet-amount');
        if (btnAmount) btnAmount.textContent = '$0';
        return;
    }
    
    const chipTypes = [
        { value: 500, class: 'chip-purple', label: '$500' },
        { value: 100, class: 'chip-gold', label: '$100' },
        { value: 50, class: 'chip-green', label: '$50' },
        { value: 25, class: 'chip-blue', label: '$25' },
        { value: 10, class: 'chip-red', label: '$10' }
    ];
    
    let remaining = betAmount;
    let delay = 0;
    
    chipTypes.forEach(chipType => {
        const count = Math.floor(remaining / chipType.value);
        remaining = remaining % chipType.value;
        
        for (let i = 0; i < count; i++) {
            const chip = document.createElement('div');
            chip.className = `chip ${chipType.class}`;
            chip.textContent = chipType.label;
            chip.style.animationDelay = (delay * 0.1) + 's';
            container.appendChild(chip);
            delay++;
        }
    });
    
    // Update totals
    const betTotal = document.getElementById('bet-total');
    if (betTotal) betTotal.textContent = '$' + betAmount.toLocaleString();
    const btnAmount = document.getElementById('btn-bet-amount');
    if (btnAmount) btnAmount.textContent = '$' + betAmount.toLocaleString();
}

// ====================
// BET ACTIONS
// ====================

function addToBet(amount) {
    if (currentBet + amount > playerChips) {
        // Can't bet more than you have
        const balanceEl = document.getElementById('chip-balance');
        if (balanceEl) shakeElement(balanceEl);
        return;
    }
    
    if (currentBet + amount > maxBet) {
        // Can't exceed max bet
        return;
    }
    
    currentBet += amount;
    updateBetChips(currentBet);
    updateSlider();
    updateChipButtons();
    
    // Play chip sound (optional)
    playChipSound();
}

function clearBet() {
    currentBet = 0;
    updateBetChips(0);
    updateSlider();
    updateChipButtons();
}

function allIn() {
    currentBet = Math.min(playerChips, maxBet);
    updateBetChips(currentBet);
    updateSlider();
    updateChipButtons();
}

function updateSlider() {
    const slider = document.getElementById('bet-slider');
    if (slider) {
        slider.value = currentBet;
    }
}

function updateChipButtons() {
    // Disable chip buttons that would exceed balance or max bet
    document.querySelectorAll('.chip-btn').forEach(btn => {
        const value = parseInt(btn.dataset.value);
        btn.disabled = (currentBet + value > playerChips) || (currentBet + value > maxBet);
    });
    
    // Disable place bet if no bet
    const placeBtn = document.getElementById('place-bet-btn');
    if (placeBtn) {
        placeBtn.disabled = currentBet < minBet;
    }
}

function placeBet() {
    if (currentBet < minBet) {
        showMessage('Minimum bet is $' + minBet, 'error');
        return;
    }
    
    if (!waitingForBet) return;
    
    console.log('[ACTION] Placing bet:', currentBet);
    
    // Hide betting panel
    const bettingPanel = document.getElementById('betting-panel');
    if (bettingPanel) {
        bettingPanel.style.display = 'none';
    }
    
    // Send bet to server
    socket.emit('place_bet', { bet: currentBet });
    waitingForBet = false;
    
    showMessage('Bet placed: $' + currentBet, 'success');
}

function updateChipBalance() {
    const balanceEl = document.getElementById('chip-balance');
    if (balanceEl) {
        balanceEl.textContent = `$${currentChips.toLocaleString()}`;
    }
    updateBalanceChips(currentChips);
}

// ====================
// UTILITY FUNCTIONS
// ====================

function shakeElement(element) {
    element.classList.add('shake');
    setTimeout(() => element.classList.remove('shake'), 500);
}

function playChipSound() {
    // Optional: Add chip sound effect
    // const audio = new Audio('/static/sounds/chip.mp3');
    // audio.volume = 0.3;
    // audio.play();
}

// Initialize slider handler when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('bet-slider');
    if (slider) {
        slider.addEventListener('input', (e) => {
            currentBet = parseInt(e.target.value);
            // Round to nearest chip value
            currentBet = Math.round(currentBet / 5) * 5;
            updateBetChips(currentBet);
            updateChipButtons();
        });
    }
});

function makeDecision(decision) {
    if (!gameState || document.getElementById('controls').style.display === 'none') {
        return;
    }
    
    disableButtons();
    socket.emit('player_decision', {decision});
    
    // Button press animation
    const button = decision === 'Hittt' ? 
        document.getElementById('hit-btn') : 
        document.getElementById('stand-btn');
    button.style.transform = 'scale(0.95)';
    setTimeout(() => {
        button.style.transform = '';
    }, 150);
    
    if (decision === 'Hittt') {
        showMessage('Hitting...', 'info');
    } else {
        showMessage('Standing...', 'info');
    }
}

// ============================================
// CARD FUNCTIONS
// ============================================

function addCard(containerId, rank, suit, isPlayer) {
    const container = document.getElementById(containerId);
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = getCardHTML(rank, suit);
    container.appendChild(card);
    
    // Flip animation
    setTimeout(() => {
        card.classList.add('flip-in');
    }, 10);
    
    // Add entrance effect
    if (isPlayer) {
        createCardGlow(card);
    }
}

function addHiddenCard(containerId) {
    const container = document.getElementById(containerId);
    const card = document.createElement('div');
    card.className = 'card hidden';
    card.innerHTML = '<div class="card-back"></div>';
    container.appendChild(card);
    
    setTimeout(() => {
        card.classList.add('flip-in');
    }, 10);
}

function getCardHTML(rank, suit) {
    const ranks = {1:'A', 11:'J', 12:'Q', 13:'K'};
    const suits = {0:'♥', 1:'♦', 2:'♣', 3:'♠'};
    const rankStr = ranks[rank] || rank;
    const suitStr = suits[suit] || '?';
    const color = (suit < 2) ? 'red' : 'black';
    
    return `
        <div class="card-front ${color}">
            <div class="card-rank-top">${rankStr}</div>
            <div class="card-suit">${suitStr}</div>
            <div class="card-rank-bottom">${rankStr}</div>
        </div>
    `;
}

function createCardGlow(card) {
    const glow = document.createElement('div');
    glow.style.cssText = `
        position: absolute;
        top: -5px;
        left: -5px;
        right: -5px;
        bottom: -5px;
        border-radius: 12px;
        background: radial-gradient(circle, rgba(255, 215, 0, 0.5), transparent);
        pointer-events: none;
        animation: glowPulse 1s ease-out;
        z-index: -1;
    `;
    card.style.position = 'relative';
    card.appendChild(glow);
    
    setTimeout(() => {
        glow.remove();
    }, 1000);
}

// ============================================
// DISPLAY FUNCTIONS
// ============================================

function updateGameDisplay() {
    if (!gameState) return;
    
    const playerValueEl = document.getElementById('player-value');
    const dealerValueEl = document.getElementById('dealer-value');
    
    if (playerValueEl) {
        playerValueEl.textContent = `Value: ${gameState.player_value}`;
        playerValueEl.classList.remove('bust');
        
        if (gameState.player_value > 21) {
            playerValueEl.classList.add('bust');
            playerValueEl.textContent += ' (BUST!)';
        } else if (gameState.player_value === 21) {
            playerValueEl.style.color = 'var(--casino-gold)';
        } else {
            playerValueEl.style.color = 'var(--casino-green)';
        }
    }
    
    if (dealerValueEl) {
        if (gameState.dealer_hidden) {
            dealerValueEl.textContent = `Value: ${gameState.dealer_value} + ?`;
            dealerValueEl.style.color = 'var(--casino-blue)';
        } else {
            dealerValueEl.textContent = `Value: ${gameState.dealer_value}`;
            dealerValueEl.classList.remove('bust');
            
            if (gameState.dealer_value > 21) {
                dealerValueEl.classList.add('bust');
                dealerValueEl.textContent += ' (BUST!)';
            } else {
                dealerValueEl.style.color = 'var(--casino-blue)';
            }
        }
    }
}

function showResult(data) {
    const resultScreen = document.getElementById('result-screen');
    const resultContainer = document.getElementById('result-container');
    const resultAnimation = document.getElementById('result-animation');
    const resultContent = document.getElementById('result-content');
    
    let emoji, text, colorClass, sound;
    
    if (data.result === 'win') {
        emoji = '🎉';
        text = `
            <h2>YOU WIN!</h2>
            <p>Your Hand: <strong>${data.player_value}</strong></p>
            <p>Dealer Hand: <strong>${data.dealer_value}</strong></p>
        `;
        colorClass = 'win';
        sound = 'win';
        createConfetti(100);
    } else if (data.result === 'loss') {
        emoji = '😞';
        text = `
            <h2>YOU LOSE</h2>
            <p>Your Hand: <strong>${data.player_value}</strong></p>
            <p>Dealer Hand: <strong>${data.dealer_value}</strong></p>
            ${data.reason === 'bust' ? '<p style="color: var(--casino-red); margin-top: 15px;">You went over 21!</p>' : ''}
        `;
        colorClass = 'loss';
        sound = 'lose';
    } else {
        emoji = '🤝';
        text = `
            <h2>PUSH!</h2>
            <p>Your Hand: <strong>${data.player_value}</strong></p>
            <p>Dealer Hand: <strong>${data.dealer_value}</strong></p>
        `;
        colorClass = 'tie';
        sound = 'tie';
    }
    
    resultAnimation.textContent = emoji;
    resultContent.innerHTML = text;
    resultContainer.className = `result-container ${colorClass}`;
    
    playSound(sound);
    showScreen('result-screen');
}

function showMessage(message, type = 'info') {
    const statusEl = document.getElementById('status-message');
    const gameMsgEl = document.getElementById('game-message');
    
    const colors = {
        'success': 'var(--casino-green)',
        'error': 'var(--casino-red)',
        'info': 'var(--casino-blue)'
    };
    
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.style.color = colors[type] || colors.info;
        statusEl.style.display = 'block';
        statusEl.style.animation = 'screenFadeIn 0.3s ease-out';
    }
    
    if (gameMsgEl) {
        gameMsgEl.textContent = message;
        gameMsgEl.style.color = colors[type] || colors.info;
        gameMsgEl.style.display = 'block';
        gameMsgEl.style.animation = 'screenFadeIn 0.3s ease-out';
    }
}

function enableButtons() {
    document.getElementById('hit-btn').disabled = false;
    document.getElementById('stand-btn').disabled = false;
}

function disableButtons() {
    document.getElementById('hit-btn').disabled = true;
    document.getElementById('stand-btn').disabled = true;
}

function playAgain() {
    showScreen('game-mode-screen');
    selectedServer = null;
    gameState = null;
    selectedGameMode = null;
    selectedCharacter = null;
    currentChips = 1000;
    resetGame();
}

function showStatistics(stats, gameMode) {
    const statsContent = document.getElementById('stats-content');
    statsContent.innerHTML = '';
    
    // Basic stats
    let html = `
        <div class="stats-section">
            <h3>📊 RESULTS</h3>
            <div class="stats-row">
                <span class="stats-label">Rounds Played:</span>
                <span class="stats-value">${stats.rounds_played}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">✅ Wins:</span>
                <span class="stats-value">${stats.wins}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">❌ Losses:</span>
                <span class="stats-value">${stats.losses}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">🤝 Ties:</span>
                <span class="stats-value">${stats.ties}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">📈 Win Rate:</span>
                <span class="stats-value">${stats.win_rate.toFixed(1)}%</span>
            </div>
        </div>
        
        <div class="stats-section">
            <h3>🔥 STREAKS</h3>
            <div class="stats-row">
                <span class="stats-label">Current Streak:</span>
                <span class="stats-value ${stats.current_streak > 0 ? 'positive' : stats.current_streak < 0 ? 'negative' : ''}">${stats.current_streak > 0 ? '+' : ''}${stats.current_streak}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">Best Win Streak:</span>
                <span class="stats-value positive">${stats.longest_win_streak}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">Worst Lose Streak:</span>
                <span class="stats-value negative">${stats.longest_lose_streak}</span>
            </div>
        </div>
        
        <div class="stats-section">
            <h3>🎰 HANDS</h3>
            <div class="stats-row">
                <span class="stats-label">Blackjacks:</span>
                <span class="stats-value">${stats.blackjacks}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">Perfect 21s:</span>
                <span class="stats-value">${stats.perfect_21s}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">Busts:</span>
                <span class="stats-value negative">${stats.busts}</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">Avg Hand Value:</span>
                <span class="stats-value">${stats.avg_hand.toFixed(1)}</span>
            </div>
        </div>
    `;
    
    if (gameMode === 2) { // Casino Mode
        html += `
            <div class="stats-section">
                <h3>💰 CASINO STATS</h3>
                <div class="stats-row">
                    <span class="stats-label">Starting Chips:</span>
                    <span class="stats-value">$${stats.starting_chips.toLocaleString()}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Current Chips:</span>
                    <span class="stats-value">$${stats.current_chips.toLocaleString()}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Total Won:</span>
                    <span class="stats-value positive">$${stats.total_won.toLocaleString()}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Total Lost:</span>
                    <span class="stats-value negative">$${stats.total_lost.toLocaleString()}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Net Profit:</span>
                    <span class="stats-value ${stats.profit >= 0 ? 'positive' : 'negative'}">${stats.profit >= 0 ? '+' : ''}$${Math.abs(stats.profit).toLocaleString()}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">ROI:</span>
                    <span class="stats-value ${stats.roi >= 0 ? 'positive' : 'negative'}">${stats.roi >= 0 ? '+' : ''}${stats.roi.toFixed(1)}%</span>
                </div>
            </div>
        `;
    } else if (gameMode === 3) { // Bot Mode
        html += `
            <div class="stats-section">
                <h3>🤖 BOT STATS</h3>
                <div class="stats-row">
                    <span class="stats-label">Total Decisions:</span>
                    <span class="stats-value">${stats.bot_decisions}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Hits:</span>
                    <span class="stats-value">${stats.bot_hits}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Stands:</span>
                    <span class="stats-value">${stats.bot_stands}</span>
                </div>
            </div>
        `;
    }
    
    statsContent.innerHTML = html;
    showScreen('stats-screen');
}

function resetGame() {
    document.getElementById('player-hand').innerHTML = '';
    document.getElementById('dealer-hand').innerHTML = '';
    document.getElementById('game-message').innerHTML = '';
    document.getElementById('round-header').innerHTML = '';
    currentRound = 0;
    totalRounds = 0;
}

// ============================================
// ANIMATION FUNCTIONS
// ============================================

function createConfetti(count) {
    const container = document.getElementById('confetti-container');
    container.innerHTML = '';
    
    const colors = ['#FFD700', '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'];
    
    for (let i = 0; i < count; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.left = Math.random() * 100 + '%';
        confetti.style.background = colors[Math.floor(Math.random() * colors.length)];
        confetti.style.width = (Math.random() * 10 + 5) + 'px';
        confetti.style.height = confetti.style.width;
        confetti.style.animationDuration = (Math.random() * 3 + 2) + 's';
        confetti.style.animationDelay = Math.random() * 0.5 + 's';
        confetti.style.borderRadius = Math.random() > 0.5 ? '50%' : '0';
        
        container.appendChild(confetti);
        
        setTimeout(() => {
            confetti.remove();
        }, 5000);
    }
}

function createShakeEffect(element) {
    element.style.animation = 'shake 0.5s';
    setTimeout(() => {
        element.style.animation = '';
    }, 500);
}

function playSound(type) {
    // Create audio context for sound effects
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    let frequency, duration;
    switch(type) {
        case 'win':
            frequency = 523.25; // C5
            duration = 0.3;
            break;
        case 'lose':
            frequency = 196.00; // G3
            duration = 0.5;
            break;
        case 'bust':
            frequency = 146.83; // D3
            duration = 0.4;
            break;
        case 'tie':
            frequency = 440.00; // A4
            duration = 0.2;
            break;
        default:
            return;
    }
    
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.value = frequency;
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + duration);
}

// Add CSS for glow pulse animation
const style = document.createElement('style');
style.textContent = `
    @keyframes glowPulse {
        0% {
            opacity: 0;
            transform: scale(0.8);
        }
        50% {
            opacity: 1;
            transform: scale(1.2);
        }
        100% {
            opacity: 0;
            transform: scale(1);
        }
    }
`;
document.head.appendChild(style);

// ============================================
// FINAL STATISTICS DISPLAY
// ============================================

function showFinalStats(stats, gameMode, broke = false) {
    console.log('[DEBUG] showFinalStats called with:', { gameMode, stats, broke });
    
    // Get game mode from stats if not provided
    if (!gameMode && stats.mode) {
        gameMode = stats.mode;
        console.log('[DEBUG] Got gameMode from stats.mode:', gameMode);
    }
    
    // Ensure gameMode is a number
    if (gameMode !== undefined && gameMode !== null) {
        gameMode = parseInt(gameMode);
    }
    
    console.log('[DEBUG] Final gameMode value:', gameMode, 'type:', typeof gameMode);
    
    // If still no gameMode, default to Classic (1)
    if (!gameMode || (gameMode !== 1 && gameMode !== 2 && gameMode !== 3)) {
        console.warn('[WARNING] Invalid gameMode, defaulting to Classic (1)');
        gameMode = 1;
    }
    
    // ========================================
    // FIRST: HIDE ALL MODE-SPECIFIC SECTIONS
    // ========================================
    console.log('[DEBUG] Hiding all mode-specific sections for gameMode:', gameMode);
    
    // Casino-only sections - HIDE by default
    const casinoSection = document.getElementById('casino-stats-section');
    const profitSection = document.getElementById('profit-stats-section');
    const doubleSection = document.getElementById('double-stats-section');
    const botSection = document.getElementById('bot-stats-section');
    const cardsSection = document.getElementById('cards-stats-section');
    
    if (casinoSection) {
        casinoSection.classList.add('hidden');
        console.log('[DEBUG] Hidden casino-stats-section');
    }
    if (profitSection) {
        profitSection.classList.add('hidden');
        console.log('[DEBUG] Hidden profit-stats-section');
    }
    if (doubleSection) {
        doubleSection.classList.add('hidden');
        console.log('[DEBUG] Hidden double-stats-section');
    }
    if (botSection) {
        botSection.classList.add('hidden');
        console.log('[DEBUG] Hidden bot-stats-section');
    }
    if (cardsSection) {
        cardsSection.classList.add('hidden');
        console.log('[DEBUG] Hidden cards-stats-section');
    }
    
    // Decisions card - shown for Classic and Casino, hidden for Bot
    const decisionsCard = document.querySelector('.decisions-card');
    if (decisionsCard) {
        if (gameMode === 3) {
            decisionsCard.classList.add('hidden');
            console.log('[DEBUG] Hidden decisions-card (Bot mode)');
        } else {
            decisionsCard.classList.remove('hidden');
            console.log('[DEBUG] Shown decisions-card (Classic/Casino mode)');
        }
    }
    
    // ========================================
    // SECTION 1: Results (ALL MODES)
    // ========================================
    document.getElementById('stat-wins').textContent = stats.wins || 0;
    document.getElementById('stat-losses').textContent = stats.losses || 0;
    document.getElementById('stat-ties').textContent = stats.ties || 0;
    
    // Animated win rate bar
    const winRate = stats.win_rate || 0;
    document.getElementById('win-rate-text').textContent = winRate.toFixed(1) + '% Win Rate';
    document.getElementById('win-rate-fill').style.width = '0%';
    setTimeout(() => {
        document.getElementById('win-rate-fill').style.width = winRate + '%';
    }, 300);
    
    // ========================================
    // SECTION 2: Streaks (ALL MODES)
    // ========================================
    document.getElementById('stat-win-streak').textContent = stats.longest_win_streak || 0;
    document.getElementById('stat-lose-streak').textContent = stats.longest_lose_streak || 0;
    
    // ========================================
    // SECTION 3: Hand Statistics (ALL MODES)
    // ========================================
    document.getElementById('stat-blackjacks').textContent = stats.blackjacks || 0;
    document.getElementById('stat-perfect21').textContent = stats.perfect_21s || 0;
    document.getElementById('stat-busts').textContent = stats.busts || 0;
    document.getElementById('stat-dealer-busts').textContent = stats.dealer_busts || 0;
    document.getElementById('stat-avg-hand').textContent = (stats.avg_hand || 0).toFixed(1);
    
    // ========================================
    // SECTION 4: Decisions (CLASSIC & CASINO ONLY)
    // ========================================
    if (gameMode !== 3) {
        document.getElementById('stat-hits').textContent = stats.total_hits || 0;
        document.getElementById('stat-stands').textContent = stats.total_stands || 0;
        document.getElementById('stat-risky-hits').textContent = stats.hits_that_busted || 0;
    }
    
    // ========================================
    // CASINO MODE (gameMode === 2)
    // ========================================
    if (gameMode === 2) {
        console.log('[DEBUG] Showing Casino Mode sections');
        // Show casino sections
        if (casinoSection) {
            casinoSection.classList.remove('hidden');
            console.log('[DEBUG] Shown casino-stats-section');
        }
        if (profitSection) {
            profitSection.classList.remove('hidden');
            console.log('[DEBUG] Shown profit-stats-section');
        }
        if (doubleSection) {
            doubleSection.classList.remove('hidden');
            console.log('[DEBUG] Shown double-stats-section');
        }
        
        // Chip Summary
        document.getElementById('chip-total').textContent = '$' + (stats.current_chips || 0).toLocaleString();
        document.getElementById('stat-start-chips').textContent = '$' + (stats.starting_chips || 0).toLocaleString();
        document.getElementById('stat-best-chips').textContent = '$' + (stats.best_chip_balance || 0).toLocaleString();
        document.getElementById('stat-worst-chips').textContent = '$' + (stats.worst_chip_balance || 0).toLocaleString();
        
        // Create animated chip visualization
        createChipVisualization(stats.current_chips || 0);
        
        // Profit & Loss
        const profit = stats.profit || 0;
        const profitEl = document.getElementById('stat-profit');
        if (profit >= 0) {
            profitEl.textContent = '+$' + profit.toLocaleString();
            profitEl.className = 'profit-value positive';
        } else {
            profitEl.textContent = '-$' + Math.abs(profit).toLocaleString();
            profitEl.className = 'profit-value negative';
        }
        
        document.getElementById('stat-total-won').textContent = '$' + (stats.total_won || 0).toLocaleString();
        document.getElementById('stat-total-lost').textContent = '$' + (stats.total_lost || 0).toLocaleString();
        document.getElementById('stat-biggest-win').textContent = '$' + (stats.biggest_win || 0).toLocaleString();
        document.getElementById('stat-biggest-loss').textContent = '$' + (stats.biggest_loss || 0).toLocaleString();
        document.getElementById('stat-roi').textContent = (stats.roi || 0).toFixed(1) + '%';
        
        // Double Down
        document.getElementById('stat-doubles').textContent = stats.double_downs || 0;
        document.getElementById('stat-doubles-won').textContent = stats.double_downs_won || 0;
        document.getElementById('stat-doubles-lost').textContent = stats.double_downs_lost || 0;
        
        // Show broke message if applicable
        if (broke) {
            const statsTitle = document.getElementById('stats-title');
            if (statsTitle) {
                statsTitle.textContent = '💸 GAME OVER - OUT OF CHIPS 💸';
                statsTitle.style.color = '#f87171';
            }
        }
    }
    
    // ========================================
    // BOT MODE (gameMode === 3)
    // ========================================
    if (gameMode === 3) {
        console.log('[DEBUG] Showing Bot Mode sections');
        // Show bot sections
        if (botSection) {
            botSection.classList.remove('hidden');
            console.log('[DEBUG] Shown bot-stats-section');
        }
        if (cardsSection) {
            cardsSection.classList.remove('hidden');
            console.log('[DEBUG] Shown cards-stats-section');
        }
        
        // Bot Performance
        const actualRate = stats.win_rate || 0;
        const expectedRate = 42.5;
        const diff = actualRate - expectedRate;
        
        document.getElementById('stat-actual-rate').textContent = actualRate.toFixed(1) + '%';
        
        const diffEl = document.getElementById('stat-vs-expected');
        if (diff >= 0) {
            diffEl.textContent = '+' + diff.toFixed(1) + '% above expected! 🎉';
            diffEl.className = 'bot-diff positive';
        } else {
            diffEl.textContent = diff.toFixed(1) + '% below expected 😔';
            diffEl.className = 'bot-diff negative';
        }
        
        document.getElementById('stat-bot-decisions').textContent = stats.bot_decisions || 0;
        document.getElementById('stat-bot-hits').textContent = stats.bot_hits || 0;
        document.getElementById('stat-bot-stands').textContent = stats.bot_stands || 0;
        
        // Card Analysis
        document.getElementById('stat-aces').textContent = stats.aces_received || 0;
        document.getElementById('stat-face-cards').textContent = stats.face_cards_received || 0;
        document.getElementById('stat-high-cards').textContent = stats.high_cards_received || 0;
        document.getElementById('stat-low-cards').textContent = stats.low_cards_received || 0;
    }
    
    // ========================================
    // SHOW THE MODAL
    // ========================================
    const modal = document.getElementById('stats-modal');
    modal.classList.remove('hidden');
}

// ========================================
// CHIP VISUALIZATION FOR CASINO MODE
// ========================================
function createChipVisualization(totalChips) {
    const container = document.getElementById('chip-stack-display');
    if (!container) return;
    
    container.innerHTML = '';
    
    const chipTypes = [
        { value: 500, class: 'chip-purple', label: '500' },
        { value: 100, class: 'chip-gold', label: '100' },
        { value: 50, class: 'chip-green', label: '50' },
        { value: 25, class: 'chip-blue', label: '25' },
        { value: 10, class: 'chip-red', label: '10' }
    ];
    
    let remaining = totalChips;
    let delay = 0;
    
    chipTypes.forEach(chipType => {
        const count = Math.floor(remaining / chipType.value);
        remaining = remaining % chipType.value;
        
        // Show max 5 chips per type
        const showCount = Math.min(count, 5);
        
        for (let i = 0; i < showCount; i++) {
            const chip = document.createElement('div');
            chip.className = 'chip ' + chipType.class;
            chip.textContent = chipType.label;
            chip.style.animationDelay = (delay * 0.1) + 's';
            container.appendChild(chip);
            delay++;
        }
    });
}

function createChipDisplay(totalChips) {
    const chipStack = document.getElementById('final-chips-display');
    chipStack.innerHTML = '';
    
    const chipValues = [
        { value: 500, color: 'purple', label: '500' },
        { value: 100, color: 'gold', label: '100' },
        { value: 50, color: 'green', label: '50' },
        { value: 25, color: 'blue', label: '25' },
        { value: 10, color: 'red', label: '10' }
    ];
    
    let remaining = totalChips;
    let chipIndex = 0;
    
    chipValues.forEach((chipType) => {
        const count = Math.floor(remaining / chipType.value);
        remaining = remaining % chipType.value;
        
        // Show max 3 chips per denomination
        for (let i = 0; i < Math.min(count, 3); i++) {
            const chip = document.createElement('div');
            chip.className = `chip ${chipType.color}`;
            chip.textContent = chipType.label;
            chip.style.animationDelay = (chipIndex * 0.1) + 's';
            chipStack.appendChild(chip);
            chipIndex++;
        }
    });
}

function playAgainFromStats() {
    const modal = document.getElementById('stats-modal');
    modal.classList.add('hidden');
    modal.classList.remove('show');
    // Reset and show game mode selection
    showGameModeSelection();
}

function showGameSetup() {
    // Alias for game mode selection
    showGameModeSelection();
}

function goHome() {
    const modal = document.getElementById('stats-modal');
    modal.classList.add('hidden');
    modal.classList.remove('show');
    document.getElementById('win-rate-fill').style.width = '0%';
    showScreen('welcome-screen');
}

// Show round result banner with score
function showRoundResultBanner(data) {
    const banner = document.getElementById('round-result-banner');
    const resultIcon = document.getElementById('result-icon');
    const resultTitle = document.getElementById('result-title');
    const resultDetails = document.getElementById('result-details');
    const dealerScoreEl = document.getElementById('dealer-score');
    const playerScoreEl = document.getElementById('player-score');
    
    if (!banner) return;
    
    let emoji, title, colorClass, sound;
    
    if (data.result === 'win') {
        emoji = '🎉';
        title = 'YOU WIN!';
        colorClass = 'win';
        sound = 'win';
        createConfetti(50);
    } else if (data.result === 'loss') {
        emoji = '😞';
        title = 'YOU LOSE';
        if (data.reason === 'bust') {
            title += ' (BUST!)';
        }
        colorClass = 'loss';
        sound = 'lose';
    } else {
        emoji = '🤝';
        title = 'PUSH!';
        colorClass = 'tie';
        sound = 'tie';
    }
    
    // Update banner content
    if (resultIcon) resultIcon.textContent = emoji;
    if (resultTitle) resultTitle.textContent = title;
    if (resultDetails) resultDetails.textContent = `Player: ${data.player_value} vs Dealer: ${data.dealer_value}`;
    if (dealerScoreEl) dealerScoreEl.textContent = dealerWins;
    if (playerScoreEl) playerScoreEl.textContent = playerWins;
    
    // Update live score banner
    updateLiveScore();
    
    // Update banner class for styling
    banner.className = `round-result-banner ${colorClass}`;
    
    // Show banner with animation
    banner.classList.remove('hidden');
    setTimeout(() => {
        banner.classList.add('show');
    }, 10);
    
    playSound(sound);
    
    // Auto-hide after 30 seconds
    if (bannerTimer) {
        clearTimeout(bannerTimer);
    }
    bannerTimer = setTimeout(() => {
        hideRoundBanner();
    }, 30000); // 30 seconds
}

function updateLiveScore() {
    const liveDealerScore = document.getElementById('live-dealer-score');
    const livePlayerScore = document.getElementById('live-player-score');
    
    if (liveDealerScore) liveDealerScore.textContent = dealerWins;
    if (livePlayerScore) livePlayerScore.textContent = playerWins;
}

function hideRoundBanner() {
    // Clear timer if exists
    if (bannerTimer) {
        clearTimeout(bannerTimer);
        bannerTimer = null;
    }
    
    const banner = document.getElementById('round-result-banner');
    if (banner) {
        banner.classList.remove('show');
        setTimeout(() => {
            banner.classList.add('hidden');
        }, 500); // Wait for fade out animation
    }
}

