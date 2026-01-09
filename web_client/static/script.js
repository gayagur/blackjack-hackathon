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

// ====================
// MULTIPLAYER STATE
// ====================
let currentRoom = null;
let isHost = false;
let isReady = false;
let myPlayerId = null;
let selectedServerForRoom = null;  // Server selected for room creation

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
    
    // Handle regular server selection (for single-player modes)
    const list = document.getElementById('servers-list');
    if (list) {
        list.innerHTML = '';
        
        if (Object.keys(servers).length === 0) {
            list.innerHTML = '<div class="status-message" style="color: #ff6b6b;">No servers found. Make sure the server is running.</div>';
        } else {
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
        }
    }
    
    // Handle room server selection (for multiplayer)
    const roomServerList = document.getElementById('room-server-list');
    if (roomServerList) {
        roomServerList.classList.remove('scanning');
        roomServerList.innerHTML = '';
        
        if (Object.keys(servers).length === 0) {
            roomServerList.innerHTML = '<div class="server-placeholder"><span class="placeholder-icon">⚠️</span><span>No servers found. Make sure the game server is running.</span></div>';
        } else {
            Object.entries(servers).forEach(([name, [ip, port]]) => {
                const serverDiv = document.createElement('div');
                serverDiv.className = 'server-option' + (selectedServerForRoom?.name === name ? ' selected' : '');
                serverDiv.innerHTML = `
                    <span class="server-name">${name}</span>
                    <span class="server-ip">${ip}:${port}</span>
                `;
                serverDiv.onclick = () => {
                    selectedServerForRoom = { name, ip, port };
                    document.querySelectorAll('#room-server-list .server-option').forEach(el => el.classList.remove('selected'));
                    serverDiv.classList.add('selected');
                    updateCreateRoomButton();
                    showMessage(`Selected server: ${name}`, 'success');
                };
                roomServerList.appendChild(serverDiv);
            });
        }
    }
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
    const errorMsg = data.message || 'An error occurred';
    showMessage(`Error: ${errorMsg}`, 'error');
    console.error('Error:', data);
    
    // If it's a fatal error, maybe redirect
    if (data.fatal) {
        setTimeout(() => {
            showScreen('game-mode-screen');
        }, 3000);
    }
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
    if (mode === 4) {
        // Multiplayer mode - go to character selection first
        showScreen('character-screen');
    } else {
        // Other modes - go to character selection
        showScreen('character-screen');
    }
}

function selectCharacter(character) {
    selectedCharacter = character;
    document.querySelectorAll('.character-card').forEach(card => {
        card.classList.remove('selected');
    });
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('selected');
    }
    
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
        if (selectedGameMode === 4) {
            // Multiplayer mode - go to lobby
            showScreen('multiplayer-lobby-screen');
        } else {
            // Other modes - go to server selection
            showScreen('server-screen');
            scanServers();
        }
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
    
    // Welcome Video Handler
    const welcomeVideo = document.getElementById('welcome-video');
    const videoContainer = document.getElementById('welcome-video-container');
    const cardShowcase = document.getElementById('card-showcase');
    
    if (welcomeVideo && videoContainer && cardShowcase) {
        // When video ends, show cards
        welcomeVideo.addEventListener('ended', function() {
            showCardsAfterVideo();
        });
        
        // Fallback: if video fails to load, show cards immediately
        welcomeVideo.addEventListener('error', function() {
            console.log('Video failed to load, showing cards');
            videoContainer.style.display = 'none';
            cardShowcase.style.display = 'flex';
        });
        
        // Optional: Allow clicking video to skip
        welcomeVideo.addEventListener('click', function() {
            welcomeVideo.pause();
            showCardsAfterVideo();
        });
    }
});

function showCardsAfterVideo() {
    const videoContainer = document.getElementById('welcome-video-container');
    const cardShowcase = document.getElementById('card-showcase');
    
    if (!videoContainer || !cardShowcase) return;
    
    // Fade out video
    videoContainer.classList.add('fade-out');
    
    // After fade out, hide video and show cards
    setTimeout(() => {
        videoContainer.style.display = 'none';
        cardShowcase.style.display = 'flex';
        cardShowcase.classList.add('fade-in');
    }, 500);
}

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
    if (!gameMode || (gameMode !== 1 && gameMode !== 2 && gameMode !== 3 && gameMode !== 4)) {
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
    if (gameMode !== 3 && gameMode !== 4) {
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
        { value: 25, color: 'blue', label: '50' },
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

// ============================================
// MULTIPLAYER FUNCTIONS
// ============================================

// ====================
// LOBBY FUNCTIONS
// ====================

function showCreateRoom() {
    document.getElementById('create-room-section').style.display = 'block';
    document.getElementById('join-room-section').style.display = 'none';
    document.querySelectorAll('.lobby-tab').forEach(t => t.classList.remove('active'));
    const tabCreate = document.getElementById('tab-create');
    if (tabCreate) tabCreate.classList.add('active');
    
    // Reset server selection
    selectedServerForRoom = null;
    updateCreateRoomButton();
}

function showJoinRoom() {
    document.getElementById('create-room-section').style.display = 'none';
    document.getElementById('join-room-section').style.display = 'block';
    document.querySelectorAll('.lobby-tab').forEach(t => t.classList.remove('active'));
    const tabJoin = document.getElementById('tab-join');
    if (tabJoin) tabJoin.classList.add('active');
}

// Rounds control
function changeRounds(delta) {
    const input = document.getElementById('mp-rounds');
    let value = parseInt(input.value) + delta;
    value = Math.max(1, Math.min(10, value));
    input.value = value;
}

// Back to game modes
function goToGameModeSelection() {
    showScreen('game-mode-screen');
}

function updateCreateRoomButton() {
    const btn = document.getElementById('create-room-btn');
    if (!btn) return;
    
    if (selectedServerForRoom) {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🎮</span><span class="btn-text">CREATE ROOM</span>';
    } else {
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⚠️</span><span class="btn-text">SELECT SERVER FIRST</span>';
    }
}

function scanServersForRoom() {
    const serverList = document.getElementById('room-server-list');
    if (serverList) {
        serverList.innerHTML = `
            <div class="scanning-animation">
                <div class="scanning-dot"></div>
                <div class="scanning-dot"></div>
                <div class="scanning-dot"></div>
            </div>
            <div style="color: #888; margin-top: 15px; text-align: center;">Scanning for servers...</div>
        `;
        serverList.classList.add('scanning');
    }
    socket.emit('scan_servers');
}

function selectServerForRoom(name, ip, port) {
    selectedServerForRoom = { name, ip, port };
    
    // Update UI - highlight selected server
    document.querySelectorAll('#room-server-list .server-option').forEach(el => {
        el.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
    
    updateCreateRoomButton();
    showMessage(`Selected server: ${name}`, 'success');
}


function createRoom() {
    if (!selectedCharacter) {
        showMessage('Please select a character first', 'error');
        showScreen('character-screen');
        return;
    }
    
    if (!selectedServerForRoom) {
        showMessage('Please select a server first', 'error');
        return;
    }
    
    const playerName = document.getElementById('host-name').value.trim() || 'Player 1';
    const numRounds = parseInt(document.getElementById('mp-rounds').value) || 5;
    const isCasino = document.getElementById('mp-casino-mode').checked;
    
    console.log('[DEBUG] Creating room:', playerName, 'with character', selectedCharacter, 'on server', selectedServerForRoom.name);
    
    socket.emit('create_room', {
        player_name: playerName,
        character: selectedCharacter,
        rounds: numRounds,
        is_casino: isCasino,
        server_ip: selectedServerForRoom.ip,
        server_port: selectedServerForRoom.port,
        server_name: selectedServerForRoom.name
    });
}

function joinRoom() {
    const playerName = document.getElementById('join-name').value.trim() || 'Player';
    const roomCode = document.getElementById('room-code').value.trim().toUpperCase();
    
    if (!roomCode) {
        showMessage('Please enter a room code', 'error');
        return;
    }
    
    socket.emit('join_room', {
        room_id: roomCode,
        player_name: playerName,
        character: selectedCharacter || 'gaya'
    });
}

function leaveRoom() {
    socket.emit('leave_room');
    currentRoom = null;
    isHost = false;
    isReady = false;
    showScreen('game-mode-screen');
}

function toggleReady() {
    isReady = !isReady;
    socket.emit('player_ready', { ready: isReady });
    
    const btn = document.getElementById('ready-btn');
    if (btn) {
        if (isReady) {
            btn.textContent = '✅ READY!';
            btn.classList.add('ready-active');
        } else {
            btn.textContent = '✋ READY';
            btn.classList.remove('ready-active');
        }
    }
}

function startMultiplayerGame() {
    // Server info is already stored in the room on backend
    // Just tell the server to start
    socket.emit('start_multiplayer_game', {});
}

// ====================
// ROOM UI UPDATES
// ====================

function updateRoomUI(roomState) {
    currentRoom = roomState;
    myPlayerId = socket.id;
    
    // Check if we're the host
    const firstPlayerSid = Object.keys(roomState.players)[0];
    isHost = (myPlayerId === firstPlayerSid);
    
    // Update room code
    const roomCodeDisplay = document.getElementById('room-code-display');
    if (roomCodeDisplay) {
        roomCodeDisplay.textContent = roomState.room_id;
    }
    
    // Update server info
    const serverInfo = document.getElementById('room-server-info');
    if (serverInfo && roomState.server_name) {
        serverInfo.style.display = 'inline';
        serverInfo.textContent = `Server: ${roomState.server_name}`;
    }
    
    // Update player count
    const playerCount = document.getElementById('player-count');
    if (playerCount) {
        playerCount.textContent = `${roomState.player_count}/${roomState.max_players} Players`;
    }
    
    // Update rounds info
    const roundsInfo = document.getElementById('rounds-info');
    if (roundsInfo) {
        roundsInfo.textContent = `${roomState.num_rounds} Rounds`;
    }
    
    // Update players list
    const playersList = document.getElementById('players-list');
    if (playersList) {
        playersList.innerHTML = '';
        
        for (const [sid, player] of Object.entries(roomState.players)) {
            const playerDiv = document.createElement('div');
            playerDiv.className = 'player-item' + (player.is_ready ? ' ready' : '');
            playerDiv.innerHTML = `
                <img src="/assests/${player.character}.png" class="player-avatar" 
                     onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%2750%27 height=%2750%27%3E%3Crect fill=%27%23ccc%27 width=%2750%27 height=%2750%27/%3E%3Ctext x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27 dy=%27.3em%27%3E${player.character.toUpperCase()}%3C/text%3E%3C/svg%3E'">
                <span class="player-name">${player.name}</span>
                <span class="player-status">${player.is_ready ? '✅' : '⏳'}</span>
            `;
            playersList.appendChild(playerDiv);
        }
    }
    
    // Show start button for host when all ready
    const startBtn = document.getElementById('start-game-btn');
    if (startBtn) {
        if (isHost && roomState.player_count >= 2) {
            const allReady = Object.values(roomState.players).every(p => p.is_ready);
            startBtn.style.display = allReady ? 'block' : 'none';
        } else {
            startBtn.style.display = 'none';
        }
    }
}

function updateMultiplayerGameUI(roomState) {
    if (!roomState) return;
    
    currentRoom = roomState;
    
    // Update round header
    document.getElementById('mp-current-round').textContent = roomState.round_num || 1;
    document.getElementById('mp-total-rounds').textContent = roomState.num_rounds || 5;
    
    // Update dealer
    updateMultiplayerDealer(roomState);
    
    // Update all players
    updateMultiplayerPlayers(roomState);
    
    // Update turn indicator
    updateTurnIndicator(roomState);
    
    // Update controls visibility
    updateMultiplayerControls(roomState);
}

function updateMultiplayerDealer(roomState) {
    const dealerCards = document.getElementById('mp-dealer-cards');
    const dealerValue = document.getElementById('mp-dealer-value');
    
    if (!dealerCards) return;
    
    dealerCards.innerHTML = '';
    
    if (roomState.dealer_hand && roomState.dealer_hand.length > 0) {
        roomState.dealer_hand.forEach((card, index) => {
            if (card && card.rank !== undefined) {
                // Visible card
                const rankDisplay = getCardRankDisplay(card.rank);
                const suitSymbol = getCardSuitSymbol(card.suit);
                const isRed = card.suit === 0 || card.suit === 1;
                const colorClass = isRed ? 'red' : 'black';
                
                const cardEl = document.createElement('div');
                cardEl.className = `card ${colorClass}`;
                cardEl.style.animationDelay = (index * 0.1) + 's';
                cardEl.innerHTML = `
                    <div class="card-corner top-left">
                        <div class="card-rank">${rankDisplay}</div>
                        <div class="card-suit">${suitSymbol}</div>
                    </div>
                    <div class="card-center-suit">${suitSymbol}</div>
                    <div class="card-corner bottom-right">
                        <div class="card-rank">${rankDisplay}</div>
                        <div class="card-suit">${suitSymbol}</div>
                    </div>
                `;
                dealerCards.appendChild(cardEl);
            } else {
                // Hidden card
                const hiddenCard = document.createElement('div');
                hiddenCard.className = 'card card-back';
                hiddenCard.innerHTML = `
                    <div class="card-back-pattern">
                        <div class="pattern-line"></div>
                        <div class="pattern-line"></div>
                        <div class="pattern-line"></div>
                    </div>
                `;
                dealerCards.appendChild(hiddenCard);
            }
        });
        
        // Calculate value display
        const hasHidden = roomState.dealer_hand.some(c => c === null);
        if (hasHidden && roomState.dealer_hand[0]) {
            const visibleValue = getCardValue(roomState.dealer_hand[0].rank);
            dealerValue.textContent = `Value: ${visibleValue} + ?`;
        } else {
            dealerValue.textContent = `Value: ${roomState.dealer_value || 0}`;
        }
    } else {
        dealerValue.textContent = 'Value: ?';
    }
}

function updateMultiplayerPlayers(roomState) {
    const playersCircle = document.getElementById('mp-players-circle');
    if (!playersCircle) return;
    
    playersCircle.innerHTML = '';
    
    const playerOrder = roomState.player_order || Object.keys(roomState.players);
    
    playerOrder.forEach((sid, index) => {
        const player = roomState.players[sid];
        if (!player) return;
        
        const isMe = sid === myPlayerId;
        const isCurrentTurn = sid === roomState.current_turn;
        
        // Build class list
        let boxClasses = ['mp-player-box'];
        if (isMe) boxClasses.push('is-you');
        if (isCurrentTurn && roomState.game_status === 'playing') boxClasses.push('current-turn');
        if (player.status) boxClasses.push(`status-${player.status}`);
        if (player.result) boxClasses.push(`result-${player.result}`);
        
        const playerBox = document.createElement('div');
        playerBox.className = boxClasses.join(' ');
        playerBox.id = `player-box-${sid}`;
        
        // Header with avatar and name
        let headerHTML = `
            <div class="mp-player-header">
                <img src="/assests/${player.character || 'gaya'}.png" 
                     class="mp-player-avatar" 
                     onerror="this.src='/assests/gaya.png'">
                <span class="mp-player-name">
                    ${player.name}
                    ${isMe ? '<span class="you-badge">YOU</span>' : ''}
                </span>
            </div>
        `;
        
        // Cards - FIX: Properly render each card
        let cardsHTML = '<div class="mp-player-cards">';
        if (player.hand && player.hand.length > 0) {
            player.hand.forEach(card => {
                if (card && card.rank !== undefined && card.suit !== undefined) {
                    // Get display values
                    const rankDisplay = getCardRankDisplay(card.rank);
                    const suitSymbol = getCardSuitSymbol(card.suit);
                    const isRed = card.suit === 0 || card.suit === 1; // Diamonds=0, Hearts=1
                    const colorClass = isRed ? 'red' : 'black';
                    
                    cardsHTML += `
                        <div class="card ${colorClass}">
                            <div class="card-corner top-left">
                                <div class="card-rank">${rankDisplay}</div>
                                <div class="card-suit">${suitSymbol}</div>
                            </div>
                            <div class="card-center-suit">${suitSymbol}</div>
                            <div class="card-corner bottom-right">
                                <div class="card-rank">${rankDisplay}</div>
                                <div class="card-suit">${suitSymbol}</div>
                            </div>
                        </div>
                    `;
                }
            });
        } else {
            cardsHTML += '<div class="no-cards">No cards yet</div>';
        }
        cardsHTML += '</div>';
        
        // Value
        let valueHTML = `<div class="mp-player-value">Value: ${player.hand_value || 0}</div>`;
        
        // Score (wins/losses) - Always show
        const playerStats = roomState.stats && roomState.stats[sid] ? roomState.stats[sid] : {};
        const wins = playerStats.wins || 0;
        const losses = playerStats.losses || 0;
        const ties = playerStats.ties || 0;
        let scoreHTML = `
            <div class="mp-player-score">
                <div class="score-wins">✅ ${wins}</div>
                <div class="score-losses">❌ ${losses}</div>
                ${ties > 0 ? `<div class="score-ties">🤝 ${ties}</div>` : ''}
            </div>
        `;
        
        // Chips (casino mode)
        let chipsHTML = '';
        if (roomState.is_casino) {
            chipsHTML = `
                <div class="mp-player-chips">
                    <div class="mp-chips-amount">$${(player.chips || 0).toLocaleString()}</div>
                    ${player.current_bet > 0 ? `<div class="mp-bet-amount">Bet: $${player.current_bet}</div>` : ''}
                </div>
            `;
        }
        
        // Result badge
        let resultHTML = '';
        if (player.result) {
            const resultText = player.result.toUpperCase();
            resultHTML = `<div class="mp-result-badge ${player.result}">${resultText}</div>`;
        }
        
        playerBox.innerHTML = headerHTML + cardsHTML + valueHTML + scoreHTML + chipsHTML + resultHTML;
        playersCircle.appendChild(playerBox);
    });
}

function updateTurnIndicator(roomState) {
    const turnBanner = document.getElementById('mp-turn-banner');
    const turnText = document.getElementById('mp-turn-text');
    
    if (!turnBanner || !turnText) return;
    
    if (roomState.game_status === 'playing' && roomState.current_turn) {
        const currentPlayer = roomState.players[roomState.current_turn];
        const isMe = roomState.current_turn === myPlayerId;
        
        turnBanner.style.display = 'block';
        
        if (isMe) {
            turnText.textContent = "🎯 YOUR TURN!";
            turnText.style.color = '#ffd700';
        } else if (currentPlayer) {
            turnText.textContent = `⏳ ${currentPlayer.name}'s turn...`;
            turnText.style.color = '#888';
        }
    } else if (roomState.game_status === 'dealer_turn') {
        turnBanner.style.display = 'block';
        turnText.textContent = "🎰 Dealer's turn...";
        turnText.style.color = '#ff6b6b';
    } else {
        turnBanner.style.display = 'none';
    }
}

function updateMultiplayerControls(roomState) {
    const controls = document.getElementById('mp-controls');
    
    if (!controls) return;
    
    const myPlayer = roomState.players[myPlayerId];
    const isMyTurn = roomState.current_turn === myPlayerId && 
                     roomState.game_status === 'playing' &&
                     myPlayer?.status === 'playing';
    
    if (isMyTurn) {
        controls.style.display = 'block';
        
        // Enable buttons
        controls.querySelectorAll('.mp-action-btn').forEach(btn => {
            btn.disabled = false;
        });
    } else {
        controls.style.display = 'none';
    }
}

// Helper functions for card display
function getCardRankDisplay(rank) {
    switch(rank) {
        case 1: return 'A';
        case 11: return 'J';
        case 12: return 'Q';
        case 13: return 'K';
        default: return rank.toString();
    }
}

function getCardSuitSymbol(suit) {
    // suit: 0=Diamonds, 1=Hearts, 2=Spades, 3=Clubs
    const suits = ['♦', '♥', '♠', '♣'];
    return suits[suit] || '?';
}

function getCardValue(rank) {
    if (rank === 1) return 11;
    if (rank >= 11) return 10;
    return rank;
}

// Legacy functions for compatibility
function getSuitSymbol(suit) {
    return getCardSuitSymbol(suit);
}

function getRankDisplay(rank) {
    return getCardRankDisplay(rank);
}

function createCardElement(rank, suit, hidden = false) {
    if (hidden) {
        const card = document.createElement('div');
        card.className = 'card card-back';
        card.innerHTML = `
            <div class="card-back-pattern">
                <div class="pattern-line"></div>
                <div class="pattern-line"></div>
                <div class="pattern-line"></div>
            </div>
        `;
        return card;
    }
    
    const card = document.createElement('div');
    const suitSymbol = getCardSuitSymbol(suit);
    const rankStr = getCardRankDisplay(rank);
    const colorClass = (suit === 0 || suit === 1) ? 'red' : 'black';
    
    card.className = `card ${colorClass}`;
    card.innerHTML = `
        <div class="card-corner top-left">
            <div class="card-rank">${rankStr}</div>
            <div class="card-suit">${suitSymbol}</div>
        </div>
        <div class="card-center-suit">${suitSymbol}</div>
        <div class="card-corner bottom-right">
            <div class="card-rank">${rankStr}</div>
            <div class="card-suit">${suitSymbol}</div>
        </div>
    `;
    
    return card;
}

// ====================
// MULTIPLAYER ACTIONS
// ====================

// Multiplayer actions
function mpHit() {
    const controls = document.getElementById('mp-controls');
    if (controls) {
        controls.querySelectorAll('.mp-action-btn').forEach(btn => btn.disabled = true);
    }
    
    socket.emit('multiplayer_decision', { decision: 'Hittt' });
}

function mpStand() {
    const controls = document.getElementById('mp-controls');
    if (controls) {
        controls.querySelectorAll('.mp-action-btn').forEach(btn => btn.disabled = true);
    }
    
    socket.emit('multiplayer_decision', { decision: 'Stand' });
}

// ====================
// MULTIPLAYER BETTING
// ====================

let mpCurrentBet = 0;
let mpPlayerChips = 1000;
let mpMinBet = 10;
let mpMaxBet = 1000;
let mpBetTimer = null;
let mpBetTimeLeft = 45;

function mpUpdateBalanceChips(balance) {
    const container = document.getElementById('mp-balance-chips');
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
            
            const visualCount = Math.min(count, 5);
            
            for (let i = 0; i < visualCount; i++) {
                const chip = document.createElement('div');
                chip.className = `chip ${chipType.class}`;
                chip.textContent = chipType.label;
                chip.style.animationDelay = (i * 0.05) + 's';
                stack.appendChild(chip);
            }
            
            if (count > 5) {
                const countBadge = document.createElement('div');
                countBadge.className = 'chip-stack-count';
                countBadge.textContent = 'x' + count;
                stack.appendChild(countBadge);
            }
            
            container.appendChild(stack);
        }
    });
    
    document.getElementById('mp-chip-balance').textContent = '$' + balance.toLocaleString();
}

function mpUpdateBetChips(betAmount) {
    const container = document.getElementById('mp-bet-chips');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (betAmount === 0) {
        container.innerHTML = '<div class="empty-bet">Click chips to bet</div>';
        document.getElementById('mp-bet-total-amount').textContent = '$0';
        document.getElementById('mp-btn-bet-amount').textContent = '$0';
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
    
    document.getElementById('mp-bet-total-amount').textContent = '$' + betAmount.toLocaleString();
    document.getElementById('mp-btn-bet-amount').textContent = '$' + betAmount.toLocaleString();
}

function mpAddToBet(amount) {
    if (mpCurrentBet + amount > mpPlayerChips) {
        shakeElement(document.getElementById('mp-chip-balance'));
        return;
    }
    
    if (mpCurrentBet + amount > mpMaxBet) {
        showMessage(`Maximum bet is $${mpMaxBet}`, 'warning');
        return;
    }
    
    mpCurrentBet += amount;
    mpUpdateBetChips(mpCurrentBet);
    mpUpdateChipButtons();
    
    playChipSound();
}

function mpClearBet() {
    mpCurrentBet = 0;
    mpUpdateBetChips(0);
    mpUpdateChipButtons();
}

function mpAllIn() {
    mpCurrentBet = Math.min(mpPlayerChips, mpMaxBet);
    mpUpdateBetChips(mpCurrentBet);
    mpUpdateChipButtons();
}

function mpUpdateChipButtons() {
    document.querySelectorAll('.mp-betting-area .chip-btn').forEach(btn => {
        const value = parseInt(btn.dataset.value);
        btn.disabled = (mpCurrentBet + value > mpPlayerChips) || (mpCurrentBet + value > mpMaxBet);
    });
    
    const placeBtn = document.getElementById('mp-place-bet-btn');
    if (placeBtn) {
        placeBtn.disabled = mpCurrentBet < mpMinBet;
    }
}

function mpConfirmBet() {
    if (mpCurrentBet < mpMinBet) {
        showMessage(`Minimum bet is $${mpMinBet}`, 'error');
        return;
    }
    
    console.log('[MP] Placing bet:', mpCurrentBet);
    
    socket.emit('multiplayer_place_bet', { bet: mpCurrentBet });
    
    // Disable betting UI
    document.getElementById('mp-place-bet-btn').disabled = true;
    document.getElementById('mp-place-bet-btn').textContent = '✅ BET PLACED!';
    document.querySelectorAll('.mp-betting-area .chip-btn').forEach(btn => btn.disabled = true);
    document.querySelector('.clear-btn').disabled = true;
    document.querySelector('.allin-btn').disabled = true;
}

function mpUpdateOtherPlayersBetting(roomState) {
    const container = document.getElementById('mp-betting-players');
    if (!container) return;
    
    container.innerHTML = '';
    
    for (const [sid, player] of Object.entries(roomState.players)) {
        if (sid === myPlayerId) continue; // Skip self
        
        const playerDiv = document.createElement('div');
        playerDiv.className = 'mp-betting-player ' + (player.bet_placed ? 'bet-placed' : 'waiting');
        playerDiv.id = `betting-player-${sid}`;
        
        playerDiv.innerHTML = `
            <img src="/assests/${player.character || 'gaya'}.png" onerror="this.src='/assests/gaya.png'">
            <div>
                <div class="player-name">${player.name}</div>
                <div class="player-status">${player.bet_placed ? '✅ Bet placed' : '⏳ Betting...'}</div>
                ${player.bet_placed && player.current_bet > 0 ? `<div class="player-bet">$${player.current_bet}</div>` : ''}
            </div>
        `;
        
        container.appendChild(playerDiv);
    }
}

function mpStartBetTimer(seconds) {
    mpBetTimeLeft = seconds;
    const timerBar = document.getElementById('mp-timer-bar');
    const timerText = document.getElementById('mp-timer-text');
    
    // Clear existing timer
    if (mpBetTimer) {
        clearInterval(mpBetTimer);
    }
    
    mpBetTimer = setInterval(() => {
        mpBetTimeLeft--;
        
        if (timerText) {
            timerText.textContent = mpBetTimeLeft + 's';
        }
        
        if (timerBar) {
            timerBar.style.width = (mpBetTimeLeft / seconds * 100) + '%';
        }
        
        // Warning colors
        if (mpBetTimeLeft <= 10) {
            timerText.style.color = '#ef4444';
        } else if (mpBetTimeLeft <= 20) {
            timerText.style.color = '#fbbf24';
        }
        
        if (mpBetTimeLeft <= 0) {
            clearInterval(mpBetTimer);
            // Auto-submit if not placed
            if (mpCurrentBet >= mpMinBet) {
                mpConfirmBet();
            }
        }
    }, 1000);
}

// ====================
// MULTIPLAYER SOCKET HANDLERS
// ====================

socket.on('room_created', (data) => {
    console.log('Room created:', data);
    isHost = true;
    myPlayerId = socket.id;
    updateRoomUI(data.room_state);
    showScreen('multiplayer-room-screen');
});

socket.on('room_joined', (data) => {
    console.log('Room joined:', data);
    myPlayerId = socket.id;
    updateRoomUI(data.room_state);
    showScreen('multiplayer-room-screen');
});

socket.on('player_joined', (data) => {
    console.log('Player joined:', data);
    updateRoomUI(data.room_state);
    // Only show message if it's not us
    if (data.player_name !== document.getElementById('join-name')?.value.trim() && 
        data.player_name !== document.getElementById('host-name')?.value.trim()) {
        showMessage(`${data.player_name} joined!`, 'success');
    }
});

socket.on('player_left', (data) => {
    console.log('Player left:', data);
    updateRoomUI(data.room_state);
    showMessage(`${data.player_name} left`, 'info');
});

socket.on('player_ready_update', (data) => {
    updateRoomUI(data.room_state);
});

socket.on('all_players_ready', (data) => {
    showMessage('All players ready! Host can start the game.', 'success');
});

socket.on('multiplayer_game_started', (data) => {
    console.log('Multiplayer game started:', data);
    showScreen('multiplayer-game-screen');
    
    // Update live score
    updateMultiplayerLiveScore(data.room_state);
    
    updateMultiplayerGameUI(data.room_state);
});

socket.on('multiplayer_round_start', (data) => {
    console.log('[MP] Round start:', data);
    showScreen('multiplayer-game-screen');
    
    // Hide betting overlay if visible
    const bettingOverlay = document.getElementById('mp-betting-overlay');
    if (bettingOverlay) {
        bettingOverlay.style.display = 'none';
    }
    
    // Hide round winner banner if visible
    const roundBanner = document.getElementById('mp-round-winner-banner');
    if (roundBanner) {
        roundBanner.style.display = 'none';
    }
    
    // Reset betting state
    mpCurrentBet = 0;
    if (mpBetTimer) {
        clearInterval(mpBetTimer);
        mpBetTimer = null;
    }
    
    updateMultiplayerGameUI(data.room_state);
    // Update live score at round start
    updateMultiplayerLiveScore(data.room_state);
});

socket.on('multiplayer_betting_phase', (data) => {
    console.log('[MP] Betting phase:', data);
    
    const myInfo = data.betting_info[myPlayerId];
    if (!myInfo) return;
    
    mpPlayerChips = myInfo.chips;
    mpMinBet = myInfo.min_bet;
    mpMaxBet = myInfo.max_bet;
    mpCurrentBet = 0;
    
    // Update round info
    document.getElementById('mp-bet-round').textContent = data.round;
    document.getElementById('mp-bet-total').textContent = data.total_rounds;
    
    // Show betting overlay
    const bettingOverlay = document.getElementById('mp-betting-overlay');
    bettingOverlay.style.display = 'flex';
    
    // RESET ALL BUTTONS - FIX: Enable all buttons for new round
    const placeBtn = document.getElementById('mp-place-bet-btn');
    if (placeBtn) {
        placeBtn.disabled = false;
        placeBtn.textContent = 'PLACE BET';
    }
    
    // Enable all chip buttons
    document.querySelectorAll('.mp-betting-area .chip-btn').forEach(btn => {
        btn.disabled = false;
    });
    
    // Enable clear and all-in buttons
    const clearBtn = document.querySelector('.mp-betting-area .clear-btn');
    const allInBtn = document.querySelector('.mp-betting-area .allin-btn');
    if (clearBtn) clearBtn.disabled = false;
    if (allInBtn) allInBtn.disabled = false;
    
    // Update chip visualization
    mpUpdateBalanceChips(mpPlayerChips);
    mpUpdateBetChips(0);
    mpUpdateChipButtons();
    
    // Update other players
    mpUpdateOtherPlayersBetting(data.room_state);
    
    // Start timer
    mpStartBetTimer(45);
    
    // Check if player can bet
    if (!myInfo.can_play) {
        showMessage('Not enough chips to continue!', 'error');
        if (placeBtn) placeBtn.disabled = true;
    }
});

// Show loading indicator when dealing starts
socket.on('multiplayer_dealing_started', (data) => {
    console.log('[MP] Dealing started');
    const loadingEl = document.getElementById('mp-dealing-loading');
    if (loadingEl) {
        loadingEl.style.display = 'block';
    }
});

// New event: All cards dealt at once (much faster)
socket.on('multiplayer_all_cards_dealt', (data) => {
    console.log('[MP] All cards dealt:', data);
    // Hide loading indicator
    const loadingEl = document.getElementById('mp-dealing-loading');
    if (loadingEl) {
        loadingEl.style.display = 'none';
    }
    // Update UI immediately with all player cards
    updateMultiplayerGameUI(data.room_state);
    // Update live score
    if (data.room_state && data.room_state.stats) {
        updateMultiplayerLiveScore(data.room_state);
    }
});

// Legacy event handler (for backward compatibility)
socket.on('multiplayer_card_dealt', (data) => {
    console.log('[MP] Card dealt:', data);
    // Update UI immediately without delay
    updateMultiplayerGameUI(data.room_state);
    // Also update live score
    if (data.room_state && data.room_state.stats) {
        updateMultiplayerLiveScore(data.room_state);
    }
});

// New event: Dealer cards dealt at once
socket.on('multiplayer_dealer_cards_dealt', (data) => {
    console.log('[MP] Dealer cards dealt:', data);
    updateMultiplayerGameUI(data.room_state);
});

// Legacy event handler (for backward compatibility)
socket.on('multiplayer_dealer_card', (data) => {
    console.log('[MP] Dealer card:', data);
    updateMultiplayerGameUI(data.room_state);
});

socket.on('multiplayer_dealing_complete', (data) => {
    console.log('[MP] Dealing complete:', data);
    updateMultiplayerGameUI(data.room_state);
    // Update live score
    updateMultiplayerLiveScore(data.room_state);
});

socket.on('multiplayer_player_turn', (data) => {
    console.log('[MP] Player turn:', data);
    updateMultiplayerGameUI(data.room_state);
    
    if (data.player_id === myPlayerId) {
        showMessage("It's your turn!", 'info');
    }
});

socket.on('multiplayer_player_hit', (data) => {
    console.log('[MP] Player hit:', data);
    updateMultiplayerGameUI(data.room_state);
});

socket.on('multiplayer_player_bust', (data) => {
    console.log('[MP] Player bust:', data);
    updateMultiplayerGameUI(data.room_state);
    
    if (data.player_id === myPlayerId) {
        showMessage('BUST! 💥', 'error');
    }
});

socket.on('multiplayer_player_stand', (data) => {
    console.log('[MP] Player stand:', data);
    updateMultiplayerGameUI(data.room_state);
});

socket.on('multiplayer_player_blackjack', (data) => {
    console.log('[MP] Player blackjack:', data);
    updateMultiplayerGameUI(data.room_state);
    
    if (data.player_id === myPlayerId) {
        showMessage('BLACKJACK! 🎰', 'success');
    }
});

socket.on('multiplayer_dealer_turn', (data) => {
    console.log('[MP] Dealer turn:', data);
    updateMultiplayerGameUI(data.room_state);
    showMessage("Dealer's turn...", 'info');
});

socket.on('multiplayer_dealer_reveal', (data) => {
    console.log('[MP] Dealer reveal:', data);
    updateMultiplayerGameUI(data.room_state);
});

socket.on('multiplayer_dealer_hit', (data) => {
    console.log('[MP] Dealer hit:', data);
    updateMultiplayerGameUI(data.room_state);
});

socket.on('multiplayer_round_results', (data) => {
    console.log('[MP] Round results:', data);
    
    // Update UI with latest stats
    updateMultiplayerGameUI(data.room_state);
    
    // Show round winner banner
    showMultiplayerRoundWinnerBanner(data.room_state);
    
    // Update live score
    updateMultiplayerLiveScore(data.room_state);
    
    // Show result for current player
    const myResult = data.room_state.players[myPlayerId]?.result;
    if (myResult === 'win') {
        createConfetti();
    }
});

socket.on('multiplayer_game_finished', (data) => {
    console.log('[MP] Game finished:', data);
    showMultiplayerFinalStats(data);
});

socket.on('multiplayer_state_update', (data) => {
    console.log('[MP] State update:', data);
    // If in betting phase, update other players
    if (data.room_state.game_status === 'betting') {
        mpUpdateOtherPlayersBetting(data.room_state);
    } else {
        updateMultiplayerGameUI(data.room_state);
    }
});

socket.on('multiplayer_player_bet', (data) => {
    console.log('[MP] Player bet:', data);
    
    // Update that player's status
    const playerDiv = document.getElementById(`betting-player-${data.player_id}`);
    if (playerDiv) {
        playerDiv.className = 'mp-betting-player bet-placed just-bet';
        playerDiv.querySelector('.player-status').textContent = '✅ Bet placed';
        
        // Add bet amount
        const betDiv = document.createElement('div');
        betDiv.className = 'player-bet';
        betDiv.textContent = '$' + data.bet_amount;
        playerDiv.querySelector('div').appendChild(betDiv);
        
        // Remove animation class after animation
        setTimeout(() => {
            playerDiv.classList.remove('just-bet');
        }, 500);
    }
    
    showMessage(`${data.player_name} bet $${data.bet_amount}`, 'info');
});

socket.on('multiplayer_all_bets_placed', (data) => {
    console.log('[MP] All bets placed:', data);
    
    // Clear timer
    if (mpBetTimer) {
        clearInterval(mpBetTimer);
        mpBetTimer = null;
    }
    
    // Reset betting state
    mpCurrentBet = 0;
    
    // Hide betting overlay with animation
    const overlay = document.getElementById('mp-betting-overlay');
    if (overlay) {
        overlay.style.animation = 'fadeOut 0.5s ease forwards';
        
        setTimeout(() => {
            overlay.style.display = 'none';
            overlay.style.animation = '';
            // Reset bet display
            mpUpdateBetChips(0);
        }, 500);
    }
    
    showMessage('All bets placed! Dealing cards...', 'success');
});

// ====================
// MULTIPLAYER FINAL STATS
// ====================

function showMultiplayerFinalStats(data) {
    console.log('[MP] Showing final stats:', data);
    
    const modal = document.getElementById('stats-modal');
    if (!modal) return;
    
    const stats = data.stats;
    const roomState = data.room_state;
    const winner = data.winner;
    
    // Update title
    const title = document.getElementById('stats-title');
    if (title) {
        title.textContent = winner && winner.id === myPlayerId ? '🎉 YOU WON! 🎉' : '🎰 GAME OVER 🎰';
    }
    
    // Get my stats
    const myStats = stats[myPlayerId] || {};
    
    // Update main stats
    document.getElementById('stat-wins').textContent = myStats.wins || 0;
    document.getElementById('stat-losses').textContent = myStats.losses || 0;
    document.getElementById('stat-ties').textContent = myStats.ties || 0;
    
    // Calculate win rate
    const total = (myStats.wins || 0) + (myStats.losses || 0) + (myStats.ties || 0);
    const winRate = total > 0 ? ((myStats.wins || 0) / total * 100).toFixed(1) : 0;
    document.getElementById('win-rate-text').textContent = `${winRate}% Win Rate`;
    document.getElementById('win-rate-fill').style.width = `${winRate}%`;
    
    // Streaks
    document.getElementById('stat-win-streak').textContent = myStats.best_win_streak || 0;
    document.getElementById('stat-lose-streak').textContent = myStats.worst_lose_streak || 0;
    
    // Special hands
    document.getElementById('stat-blackjacks').textContent = myStats.blackjacks || 0;
    document.getElementById('stat-busts').textContent = myStats.busts || 0;
    document.getElementById('stat-dealer-busts').textContent = myStats.dealer_busts || 0;
    
    // Hide all mode-specific sections
    document.querySelectorAll('.stats-card').forEach(card => {
        if (card.id !== 'results-card' && card.id !== 'streaks-card' && card.id !== 'special-card') {
            card.classList.add('hidden');
        }
    });
    
    // Show multiplayer stats section
    let mpStatsHTML = `
        <div class="stats-card" id="multiplayer-stats-section">
            <div class="stats-card-header">👥 Multiplayer Results</div>
            <div class="mp-stats-players">
    `;
    
    // Sort players by wins (or chips in casino mode)
    const playersList = Object.entries(roomState.players).map(([sid, player]) => {
        const playerStats = stats[sid] || {};
        return {
            sid,
            player,
            stats: playerStats,
            isMe: sid === myPlayerId,
            isWinner: sid === winner.id
        };
    });
    
    if (roomState.is_casino) {
        playersList.sort((a, b) => (b.player.chips || 0) - (a.player.chips || 0));
    } else {
        playersList.sort((a, b) => (b.stats.wins || 0) - (a.stats.wins || 0));
    }
    
    playersList.forEach(({sid, player, stats: playerStats, isMe, isWinner}, index) => {
        const rank = index + 1;
        const rankEmoji = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `${rank}.`;
        
        mpStatsHTML += `
            <div class="mp-stat-player ${isMe ? 'is-me' : ''} ${isWinner ? 'is-winner' : ''}">
                <div class="mp-stat-rank">${rankEmoji}</div>
                <div class="mp-stat-avatar">
                    <img src="/assests/${player.character || 'gaya'}.png" onerror="this.src='/assests/gaya.png'">
                </div>
                <div class="mp-stat-info">
                    <div class="mp-stat-name">
                        ${player.name}
                        ${isMe ? '<span class="you-badge">YOU</span>' : ''}
                        ${isWinner ? '<span class="winner-badge">🏆 WINNER</span>' : ''}
                    </div>
                    <div class="mp-stat-details">
                        <div class="mp-stat-item">
                            <span>✅ Wins:</span>
                            <span class="stat-value">${playerStats.wins || 0}</span>
                        </div>
                        <div class="mp-stat-item">
                            <span>❌ Losses:</span>
                            <span class="stat-value">${playerStats.losses || 0}</span>
                        </div>
                        <div class="mp-stat-item">
                            <span>🤝 Ties:</span>
                            <span class="stat-value">${playerStats.ties || 0}</span>
                        </div>
                        ${roomState.is_casino ? `
                        <div class="mp-stat-item">
                            <span>💰 Chips:</span>
                            <span class="stat-value">$${(player.chips || 0).toLocaleString()}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    mpStatsHTML += `
            </div>
        </div>
    `;
    
    // Remove old multiplayer stats if exists
    const oldMpStats = document.getElementById('multiplayer-stats-section');
    if (oldMpStats) {
        oldMpStats.remove();
    }
    
    // Add new multiplayer stats
    const statsContent = document.querySelector('.stats-content');
    if (statsContent) {
        statsContent.insertAdjacentHTML('beforeend', mpStatsHTML);
    }
    
    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('show');
}

// ====================
// MULTIPLAYER ROUND WINNER BANNER
// ====================

function showMultiplayerRoundWinnerBanner(roomState) {
    const banner = document.getElementById('mp-round-winner-banner');
    const icon = document.getElementById('mp-winner-icon');
    const text = document.getElementById('mp-winner-text');
    const details = document.getElementById('mp-winner-details');
    
    if (!banner) return;
    
    // Calculate winners
    const winners = [];
    const losers = [];
    const ties = [];
    
    Object.entries(roomState.players).forEach(([sid, player]) => {
        if (player.result === 'win') {
            winners.push(player);
        } else if (player.result === 'loss') {
            losers.push(player);
        } else if (player.result === 'tie') {
            ties.push(player);
        }
    });
    
    // Determine banner content
    const myPlayer = roomState.players[myPlayerId];
    const myResult = myPlayer?.result;
    
    if (winners.length > 0) {
        if (myResult === 'win') {
            icon.textContent = '🎉';
            text.textContent = 'YOU WIN!';
            text.className = 'winner-text win';
            details.innerHTML = `
                <div class="winner-list">
                    ${winners.map(p => `<div class="winner-name">${p.name}</div>`).join('')}
                </div>
            `;
        } else {
            icon.textContent = '😔';
            text.textContent = 'YOU LOST';
            text.className = 'winner-text loss';
            details.innerHTML = `
                <div class="winner-list">
                    <div>Winners:</div>
                    ${winners.map(p => `<div class="winner-name">${p.name}</div>`).join('')}
                </div>
            `;
        }
    } else if (myResult === 'tie') {
        icon.textContent = '🤝';
        text.textContent = 'TIE!';
        text.className = 'winner-text tie';
        details.innerHTML = '<div>It\'s a tie!</div>';
    } else {
        icon.textContent = '😔';
        text.textContent = 'YOU LOST';
        text.className = 'winner-text loss';
        details.innerHTML = '<div>Better luck next round!</div>';
    }
    
    banner.style.display = 'flex';
    banner.classList.add('show');
}

function hideRoundWinnerBanner() {
    const banner = document.getElementById('mp-round-winner-banner');
    if (banner) {
        banner.classList.remove('show');
        setTimeout(() => {
            banner.style.display = 'none';
        }, 500);
    }
}

// ====================
// MULTIPLAYER LIVE SCORE
// ====================

function updateMultiplayerLiveScore(roomState) {
    const scoreContent = document.getElementById('mp-live-score-content');
    if (!scoreContent) return;
    
    scoreContent.innerHTML = '';
    
    // Get all players with their stats
    const playersList = Object.entries(roomState.players).map(([sid, player]) => {
        const playerStats = roomState.stats && roomState.stats[sid] ? roomState.stats[sid] : {};
        return {
            sid,
            player,
            stats: playerStats,
            isMe: sid === myPlayerId
        };
    });
    
    // Sort by wins (descending)
    playersList.sort((a, b) => (b.stats.wins || 0) - (a.stats.wins || 0));
    
    // Add dealer score
    let dealerWins = 0;
    Object.values(roomState.players).forEach(player => {
        if (player.result === 'loss') {
            dealerWins++;
        }
    });
    
    // Add dealer item
    const dealerItem = document.createElement('div');
    dealerItem.className = 'score-item dealer-item';
    dealerItem.innerHTML = `
        <div class="score-label">Dealer</div>
        <div class="score-value dealer-score">${dealerWins}</div>
    `;
    scoreContent.appendChild(dealerItem);
    
    // Add separator
    const separator = document.createElement('div');
    separator.className = 'score-separator';
    scoreContent.appendChild(separator);
    
    // Add each player
    playersList.forEach(({sid, player, stats, isMe}) => {
        const wins = stats.wins || 0;
        const losses = stats.losses || 0;
        const ties = stats.ties || 0;
        
        const playerItem = document.createElement('div');
        playerItem.className = `score-item ${isMe ? 'is-me' : ''}`;
        playerItem.innerHTML = `
            <div class="score-label">
                ${isMe ? '⭐ ' : ''}${player.name}
            </div>
            <div class="score-value">${wins}</div>
        `;
        scoreContent.appendChild(playerItem);
    });
}

// Reset score when game starts
socket.on('multiplayer_game_started', (data) => {
    updateMultiplayerLiveScore(data.room_state);
});

// ====================
// EXIT GAME FUNCTIONS
// ====================

function showExitConfirmation() {
    document.getElementById('exit-confirmation-modal').style.display = 'flex';
}

function hideExitConfirmation() {
    document.getElementById('exit-confirmation-modal').style.display = 'none';
}

function confirmExitGame() {
    console.log('[MP] Leaving game...');
    
    // Hide modal
    hideExitConfirmation();
    
    // Leave the room on server
    socket.emit('leave_room');
    
    // Reset multiplayer state
    currentRoom = null;
    isHost = false;
    isReady = false;
    myPlayerId = null;
    
    // Hide betting overlay if visible
    const bettingOverlay = document.getElementById('mp-betting-overlay');
    if (bettingOverlay) {
        bettingOverlay.style.display = 'none';
    }
    
    // Clear any timers
    if (mpBetTimer) {
        clearInterval(mpBetTimer);
        mpBetTimer = null;
    }
    
    // Go back to welcome screen
    showScreen('welcome-screen');
    
    showMessage('You left the game', 'info');
}

// Also add exit button to waiting room
function addExitToWaitingRoom() {
    const waitingRoom = document.getElementById('multiplayer-room-screen');
    if (waitingRoom && !waitingRoom.querySelector('.mp-exit-btn')) {
        const exitBtn = document.createElement('button');
        exitBtn.className = 'mp-exit-btn';
        exitBtn.onclick = showExitConfirmation;
        exitBtn.innerHTML = `
            <span class="exit-icon">✕</span>
            <span class="exit-text">Leave Room</span>
        `;
        waitingRoom.insertBefore(exitBtn, waitingRoom.firstChild);
    }
}

// Handle being kicked/disconnected
socket.on('room_closed', (data) => {
    console.log('[MP] Room closed:', data);
    
    currentRoom = null;
    isHost = false;
    
    hideExitConfirmation();
    
    const bettingOverlay = document.getElementById('mp-betting-overlay');
    if (bettingOverlay) {
        bettingOverlay.style.display = 'none';
    }
    
    showScreen('welcome-screen');
    showMessage(data.message || 'Room was closed', 'warning');
});

// Handle host leaving
socket.on('host_left', (data) => {
    console.log('[MP] Host left:', data);
    showMessage('Host left the game. Returning to menu...', 'warning');
    
    setTimeout(() => {
        confirmExitGame();
    }, 2000);
});

// Handle player disconnected during game
socket.on('player_disconnected', (data) => {
    console.log('[MP] Player disconnected:', data);
    updateMultiplayerGameUI(data.room_state);
    showMessage(`${data.player_name} disconnected`, 'warning');
});

// Handle game ended due to not enough players
socket.on('game_ended_not_enough_players', (data) => {
    console.log('[MP] Game ended - not enough players:', data);
    showMessage('Game ended: Not enough players to continue', 'warning');
    
    setTimeout(() => {
        confirmExitGame();
    }, 2000);
});

socket.on('new_host', (data) => {
    isHost = (data.host_id === myPlayerId);
    updateRoomUI(data.room_state);
    if (isHost) {
        showMessage('You are now the host!', 'info');
    }
});
