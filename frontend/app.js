// J.A.R.V.I.S. Frontend Logic

const API_BASE = ''; // same origin
let isMicOn = false;
let isVoiceOn = true;
let wakeWordEnabled = true;
let recognition = null;
let synth = window.speechSynthesis;
let isListening = false;
let isSpeaking = false;
let websocket = null;

// Elements
const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const voiceBtn = document.getElementById('voice-btn');
const clearBtn = document.getElementById('clear-btn');
const wakeBtn = document.getElementById('wake-btn');
const stateText = document.getElementById('state-text');
const stateIndicator = document.getElementById('state-indicator');
const stateDot = document.getElementById('state-dot');
const toolLog = document.getElementById('tool-log');
const memoryList = document.getElementById('memory-list');
const reminderList = document.getElementById('reminder-list');
const visualizer = document.getElementById('visualizer');
const timeDisplay = document.getElementById('time-display');
const llmStatus = document.getElementById('llm-status');
const modeDisplay = document.getElementById('mode-display');

// Init visualizer bars
for (let i = 0; i < 20; i++) {
    const bar = document.createElement('div');
    bar.className = 'v-bar';
    visualizer.appendChild(bar);
}
const vBars = document.querySelectorAll('.v-bar');

function randomVisualizer(active = false) {
    vBars.forEach((bar, idx) => {
        if (active) {
            const height = 4 + Math.random() * 26 + Math.sin(Date.now()/200 + idx)*10;
            bar.style.height = `${height}px`;
            bar.classList.add('active');
        } else {
            bar.style.height = `${4 + Math.sin(Date.now()/800 + idx)*2}px`;
            bar.classList.remove('active');
        }
    });
}

// Canvas core animation
const canvas = document.getElementById('core-canvas');
const ctx = canvas.getContext('2d');

function resizeCanvas() {
    canvas.width = canvas.offsetWidth * window.devicePixelRatio;
    canvas.height = canvas.offsetHeight * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
}

function drawCore() {
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    const cx = w/2;
    const cy = h/2;

    ctx.clearRect(0,0,w,h);
    
    // Grid rings
    const time = Date.now()/1000;
    for (let r = 40; r < 180; r+=25) {
        ctx.beginPath();
        ctx.arc(cx, cy, r + Math.sin(time*0.5 + r*0.01)*2, 0, Math.PI*2);
        ctx.strokeStyle = `rgba(0,212,255,${0.15 - r*0.0005})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
    }

    // Rotating ticks
    ctx.save();
    ctx.translate(cx,cy);
    ctx.rotate(time*0.3);
    for (let i=0; i<12; i++) {
        ctx.rotate(Math.PI/6);
        ctx.beginPath();
        ctx.moveTo(70,0);
        ctx.lineTo(75,0);
        ctx.strokeStyle = `rgba(0,212,255,${0.2 + Math.sin(time*2 + i)*0.2})`;
        ctx.lineWidth = 1;
        ctx.stroke();
    }
    ctx.restore();

    ctx.save();
    ctx.translate(cx,cy);
    ctx.rotate(-time*0.5);
    for (let i=0; i<8; i++) {
        ctx.rotate(Math.PI/4);
        ctx.beginPath();
        ctx.moveTo(90,0);
        ctx.lineTo(100,0);
        ctx.strokeStyle = `rgba(0,212,255,0.15)`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
    }
    ctx.restore();

    requestAnimationFrame(drawCore);
}

// Clock
function updateClock() {
    const now = new Date();
    timeDisplay.textContent = now.toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

// Status fetch
async function fetchStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();
        
        document.getElementById('cpu-text').textContent = `${Math.round(data.system.cpu_percent)||45}%`;
        document.getElementById('cpu-bar').style.width = `${data.system.cpu_percent||45}%`;
        document.getElementById('mem-text').textContent = `${Math.round(data.system.memory_percent)||62}%`;
        document.getElementById('mem-bar').style.width = `${data.system.memory_percent||62}%`;
        
        if (data.llm_enabled) {
            llmStatus.textContent = `AI: GPT MODE`;
            llmStatus.style.color = '#00ff88';
            modeDisplay.textContent = 'LLM Mode (GPT)';
        } else {
            llmStatus.textContent = `AI: LOCAL MODE`;
            llmStatus.style.color = '#00d4ff';
            modeDisplay.textContent = 'Rule-Based Mode';
        }
    } catch (e) {
        console.log('Status fetch failed', e);
    }
}
setInterval(fetchStatus, 5000);
fetchStatus();

async function fetchMemories() {
    try {
        const res = await fetch(`${API_BASE}/api/memory`);
        const data = await res.json();
        if (data.memories && Object.keys(data.memories).length > 0) {
            memoryList.innerHTML = Object.entries(data.memories).map(([k,v]) => 
                `<div class="mem-item"><strong>${k}:</strong> ${v.value.slice(0,60)}</div>`
            ).join('');
        } else {
            memoryList.innerHTML = '<div class="empty">No memories stored</div>';
        }
    } catch {}
}

async function fetchReminders() {
    try {
        const res = await fetch(`${API_BASE}/api/reminders`);
        const data = await res.json();
        const pending = data.pending || [];
        if (pending.length > 0) {
            reminderList.innerHTML = pending.map(r => 
                `<div class="mem-item">${r.id}. ${r.text} <small style="color:#6a8aaa">(${r.time})</small></div>`
            ).join('');
        } else {
            reminderList.innerHTML = '<div class="empty">All clear, Sir</div>';
        }
    } catch {}
}
setInterval(() => { fetchMemories(); fetchReminders(); }, 4000);
fetchMemories(); fetchReminders();

// Voice animation loop
let visInterval = setInterval(() => {
    randomVisualizer(isSpeaking || isListening);
}, 80);

// Chat functions
function addMessage(text, sender = 'jarvis', meta = '') {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    div.innerHTML = `
        <div class="content">${formatMessage(text)}</div>
        ${meta ? `<div class="meta">${meta}</div>` : ''}
    `;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return div;
}

function formatMessage(text) {
    // Simple markdown-like
    return text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code style="background:rgba(0,212,255,0.15); padding:2px 6px; border-radius:3px; font-family:Share Tech Mono;">$1</code>');
}

function updateState(state, text) {
    stateIndicator.className = 'state-indicator ' + state;
    stateText.textContent = text;
    if (state === 'listening') {
        isListening = true;
        stateDot.style.background = '#00ff88';
    } else if (state === 'speaking') {
        isSpeaking = true;
        isListening = false;
        stateDot.style.background = '#ffaa00';
    } else if (state === 'thinking') {
        isListening = false;
        isSpeaking = false;
        stateDot.style.background = '#00d4ff';
    } else {
        isListening = false;
        isSpeaking = false;
        stateDot.style.background = '#00d4ff';
    }
}

function addToolLog(toolCalls) {
    if (!toolCalls || toolCalls.length === 0) return;
    
    // clear empty
    if (toolLog.querySelector('.log-empty')) toolLog.innerHTML = '';

    toolCalls.forEach(tc => {
        const div = document.createElement('div');
        div.className = 'log-item';
        const argsStr = JSON.stringify(tc.args || {}).slice(0,80);
        const resultStr = JSON.stringify(tc.result || {}).slice(0,120);
        div.innerHTML = `
            <div class="t-name">> ${tc.tool}</div>
            <div class="t-args">${argsStr}</div>
            <div class="t-result">${resultStr}</div>
        `;
        toolLog.prepend(div);
    });

    // Limit
    while (toolLog.children.length > 20) {
        toolLog.removeChild(toolLog.lastChild);
    }
}

// JARVIS voice
function speak(text) {
    if (!isVoiceOn) return;
    
    // Stop any current
    synth.cancel();

    // Clean text for speech
    const cleanText = text.replace(/[*`_#]/g, '').replace(/<br>/g, '. ').slice(0,500);

    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    // Try to get a nice voice - prefer UK male if available
    const voices = synth.getVoices();
    let preferred = voices.find(v => v.name.includes('Google UK English Male')) ||
                    voices.find(v => v.name.includes('UK') && v.name.includes('Male')) ||
                    voices.find(v => v.lang === 'en-GB') ||
                    voices.find(v => v.lang.startsWith('en')) ;
    
    if (preferred) utterance.voice = preferred;
    utterance.rate = 1.0;
    utterance.pitch = 0.9;
    utterance.volume = 0.9;

    utterance.onstart = () => updateState('speaking', 'SPEAKING...');
    utterance.onend = () => {
        updateState('idle', wakeWordEnabled ? 'IDLE - Listening for "Jarvis"' : 'IDLE');
        isSpeaking = false;
    };
    utterance.onerror = () => {
        updateState('idle', 'IDLE');
        isSpeaking = false;
    };

    synth.speak(utterance);
}

// Send message to backend
async function sendMessage(text) {
    if (!text.trim()) return;

    addMessage(text, 'user', new Date().toLocaleTimeString());
    userInput.value = '';
    updateState('thinking', 'PROCESSING...');

    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text})
        });
        const data = await res.json();
        
        addMessage(data.response, 'jarvis', `${data.mode} • ${new Date().toLocaleTimeString()}`);
        addToolLog(data.tool_calls);
        
        updateState('idle', wakeWordEnabled ? 'IDLE - Listening for "Jarvis"' : 'IDLE');
        speak(data.response);

        fetchMemories();
        fetchReminders();

    } catch (e) {
        addMessage(`Connection error, Sir. ${e.message} - Backend may be offline.`, 'jarvis', 'error');
        updateState('idle', 'ERROR - Check backend');
        console.error(e);
    }
}

// Speech Recognition
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        micBtn.style.display = 'none';
        wakeBtn.style.display = 'none';
        addMessage('Voice recognition not supported in this browser, Sir. Try Chrome or Edge.', 'jarvis', 'system');
        return null;
    }

    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';

    let finalTranscript = '';

    rec.onstart = () => {
        isMicOn = true;
        micBtn.classList.add('active');
        micBtn.querySelector('span').textContent = 'MIC ON';
        updateState('listening', 'LISTENING...');
    };

    rec.onend = () => {
        if (isMicOn) {
            // Restart if still supposed to be on
            try { rec.start(); } catch (e) {}
        } else {
            micBtn.classList.remove('active');
            micBtn.querySelector('span').textContent = 'MIC OFF';
            updateState('idle', wakeWordEnabled ? 'IDLE - Listening for "Jarvis"' : 'IDLE');
        }
    };

    rec.onerror = (e) => {
        console.log('Speech error', e.error);
        if (e.error === 'not-allowed') {
            isMicOn = false;
            micBtn.classList.remove('active');
            addMessage('Microphone permission denied, Sir. Please allow mic access.', 'jarvis', 'error');
        }
    };

    rec.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
                handleVoiceResult(transcript.trim());
            } else {
                interim += transcript;
            }
        }
        
        if (interim) {
            stateText.textContent = `HEARING: "${interim.slice(-40)}"`;
        }
    };

    return rec;
}

function handleVoiceResult(transcript) {
    if (!transcript) return;
    const lower = transcript.toLowerCase();

    if (wakeWordEnabled) {
        // Check for wake word
        if (lower.includes('jarvis') || lower.includes('travis') || lower.includes('service')) {
            // Remove wake word and send command
            let command = transcript
                .replace(/jarvis/gi, '')
                .replace(/travis/gi, '')
                .replace(/hey/gi, '')
                .trim();
            
            // If just "Jarvis", greet
            if (command.length < 2) {
                command = "Hello";
            }

            // Visual feedback
            addMessage(`🎤 ${transcript}`, 'user', 'voice');
            sendMessage(command);
        } else {
            // If mic is on without wake word mode is off? handle differently
            if (!wakeWordEnabled && isMicOn) {
                // Direct command without wake word
                if (lower.length > 2) {
                    addMessage(`🎤 ${transcript}`, 'user', 'voice');
                    sendMessage(transcript);
                }
            }
        }
    } else {
        // Wake word disabled, direct listening
        if (lower.length > 2) {
            addMessage(`🎤 ${transcript}`, 'user', 'voice');
            sendMessage(transcript);
        }
    }
}

// Event Listeners
sendBtn.addEventListener('click', () => {
    sendMessage(userInput.value);
});

userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage(userInput.value);
});

micBtn.addEventListener('click', () => {
    if (!recognition) {
        recognition = initSpeechRecognition();
        if (!recognition) return;
    }

    if (isMicOn) {
        isMicOn = false;
        recognition.stop();
        micBtn.classList.remove('active');
        micBtn.querySelector('span').textContent = 'MIC OFF';
        updateState('idle', wakeWordEnabled ? 'IDLE - Listening for "Jarvis"' : 'IDLE');
    } else {
        try {
            recognition.start();
        } catch (e) {
            // Already started
            recognition.stop();
            setTimeout(() => recognition.start(), 250);
        }
    }
});

voiceBtn.addEventListener('click', () => {
    isVoiceOn = !isVoiceOn;
    voiceBtn.classList.toggle('active', isVoiceOn);
    voiceBtn.querySelector('span').textContent = isVoiceOn ? 'VOICE ON' : 'VOICE OFF';
    if (!isVoiceOn) synth.cancel();
});

clearBtn.addEventListener('click', async () => {
    chatContainer.innerHTML = '';
    toolLog.innerHTML = '<div class="log-empty">Awaiting commands, Sir</div>';
    try {
        await fetch(`${API_BASE}/api/clear-history`, {method: 'POST'});
    } catch {}
    addMessage('Memory cleared. How may I assist, Sir?', 'jarvis', 'system');
});

wakeBtn.addEventListener('click', () => {
    wakeWordEnabled = !wakeWordEnabled;
    wakeBtn.classList.toggle('active', wakeWordEnabled);
    wakeBtn.querySelector('span').textContent = `WAKE WORD: ${wakeWordEnabled ? 'ON' : 'OFF'}`;
    updateState('idle', wakeWordEnabled ? 'IDLE - Listening for "Jarvis"' : 'IDLE - Mic direct mode');
});

document.querySelectorAll('.sug').forEach(el => {
    el.addEventListener('click', () => {
        sendMessage(el.dataset.cmd);
    });
});

document.querySelectorAll('.q-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const action = btn.dataset.action;
        if (action === 'time') sendMessage("What's the time?");
        if (action === 'weather') sendMessage("What's the weather?");
        if (action === 'system') sendMessage("System status report");
        if (action === 'clear-memory') {
            if (confirm('Clear all memories?')) {
                const res = await fetch(`${API_BASE}/api/memory`);
                const data = await res.json();
                for (let k of Object.keys(data.memories || {})) {
                    await fetch(`${API_BASE}/api/memory/${k}`, {method: 'DELETE'});
                }
                fetchMemories();
                addMessage('All memories wiped, Sir.', 'jarvis');
            }
        }
    });
});

// Auto greeting
window.addEventListener('load', () => {
    resizeCanvas();
    drawCore();
    
    // Wait for voices
    if (synth.onvoiceschanged !== undefined) {
        synth.onvoiceschanged = () => synth.getVoices();
    }

    setTimeout(() => {
        const hour = new Date().getHours();
        let greet = 'evening';
        if (hour < 12) greet = 'morning';
        else if (hour < 18) greet = 'afternoon';
        
        const welcome = `Good ${greet}, Sir. J.A.R.V.I.S. online. All systems nominal. I'm ready to assist. You can type, or click MIC and say "Jarvis, what's the time?"`;
        addMessage(welcome, 'jarvis', 'boot sequence complete');

        // Try websocket
        connectWebSocket();
    }, 800);
});

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;
    try {
        websocket = new WebSocket(wsUrl);
        websocket.onopen = () => {
            console.log('WS connected');
        };
        websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'response') {
                    // handled via fetch, but can use ws too
                }
            } catch {}
        };
        websocket.onerror = () => {
            console.log('WS error, using HTTP');
        };
    } catch (e) {
        console.log('WS not available');
    }
}

// Handle page visibility to pause recognition
document.addEventListener('visibilitychange', () => {
    if (document.hidden && isMicOn && recognition) {
        // keep running
    }
});
