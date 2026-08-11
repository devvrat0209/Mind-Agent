// J.A.R.V.I.S. OS 2.0 - Real HUD with Built-in Browser + Live Logs
const API_BASE = '';
let isMicOn = false, isVoiceOn = true, wakeWordEnabled = true;
let recognition = null, synth = window.speechSynthesis;
let isListening = false, isSpeaking = false, websocket = null;
let queryCount = 0, bootTime = Date.now(), logsPaused = false, useProxy = false;
let currentBrowserUrl = "https://duckduckgo.com";

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
const logsStream = document.getElementById('logs-stream');
const arenaConversationEl = document.getElementById('arena-conversation');
const intelResultsEl = document.getElementById('intel-results');
const fileExplorerEl = document.getElementById('file-explorer');

// Init visualizer
for (let i = 0; i < 24; i++) {
  const bar = document.createElement('div'); bar.className = 'v-bar'; visualizer.appendChild(bar);
}
const vBars = document.querySelectorAll('.v-bar');
function randomVisualizer(active = false) {
  vBars.forEach((bar, idx) => {
    if (active) {
      const h = 4 + Math.random() * 28 + Math.sin(Date.now()/150 + idx)*8;
      bar.style.height = `${h}px`; bar.classList.add('active');
    } else {
      bar.style.height = `${3 + Math.sin(Date.now()/700 + idx)*2}px`; bar.classList.remove('active');
    }
  });
}
setInterval(() => randomVisualizer(isSpeaking || isListening), 70);

// Background Canvas - Particle field + Hex
const bgCanvas = document.getElementById('bg-canvas');
const bgCtx = bgCanvas.getContext('2d');
let particles = [];
function resizeBg() {
  bgCanvas.width = window.innerWidth; bgCanvas.height = window.innerHeight;
  particles = Array.from({length: 80}, () => ({
    x: Math.random()*bgCanvas.width,
    y: Math.random()*bgCanvas.height,
    vx: (Math.random()-0.5)*0.5,
    vy: (Math.random()-0.5)*0.5,
    size: Math.random()*1.5+0.5,
    alpha: Math.random()*0.5+0.2
  }));
}
function drawBg() {
  bgCtx.clearRect(0,0,bgCanvas.width, bgCanvas.height);
  // particles
  particles.forEach(p=>{
    p.x+=p.vx; p.y+=p.vy;
    if(p.x<0||p.x>bgCanvas.width) p.vx*=-1;
    if(p.y<0||p.y>bgCanvas.height) p.vy*=-1;
    bgCtx.fillStyle = `rgba(0,212,255,${p.alpha*0.6})`;
    bgCtx.beginPath(); bgCtx.arc(p.x,p.y,p.size,0,Math.PI*2); bgCtx.fill();
  });
  // connections
  for(let i=0;i<particles.length;i++){
    for(let j=i+1;j<particles.length;j++){
      const dx=particles[i].x-particles[j].x, dy=particles[i].y-particles[j].y;
      const dist=Math.sqrt(dx*dx+dy*dy);
      if(dist<120){
        bgCtx.strokeStyle=`rgba(0,212,255,${0.08*(1-dist/120)})`;
        bgCtx.lineWidth=0.5; bgCtx.beginPath();
        bgCtx.moveTo(particles[i].x,particles[i].y); bgCtx.lineTo(particles[j].x,particles[j].y); bgCtx.stroke();
      }
    }
  }
  requestAnimationFrame(drawBg);
}
window.addEventListener('resize', resizeBg);
resizeBg(); drawBg();

// Core Canvas - Real Jarvis reactor
const coreCanvas = document.getElementById('core-canvas');
const coreCtx = coreCanvas.getContext('2d');
function resizeCore(){
  coreCanvas.width = coreCanvas.offsetWidth * window.devicePixelRatio;
  coreCanvas.height = coreCanvas.offsetHeight * window.devicePixelRatio;
  coreCtx.setTransform(1,0,0,1,0,0);
  coreCtx.scale(window.devicePixelRatio, window.devicePixelRatio);
}
function drawCore(){
  const w = coreCanvas.offsetWidth, h = coreCanvas.offsetHeight, cx=w/2, cy=h/2;
  coreCtx.clearRect(0,0,w,h);
  const t = Date.now()/1000;
  // rings
  for(let r=35; r<200; r+=18){
    coreCtx.beginPath();
    coreCtx.arc(cx, cy, r + Math.sin(t*0.6 + r*0.02)*1.5, 0, Math.PI*2);
    coreCtx.strokeStyle = `rgba(0,212,255,${0.18 - r*0.0007})`;
    coreCtx.lineWidth = r%36===0?1:0.5;
    coreCtx.stroke();
  }
  // ticks
  coreCtx.save(); coreCtx.translate(cx,cy); coreCtx.rotate(t*0.25);
  for(let i=0;i<16;i++){ coreCtx.rotate(Math.PI/8); coreCtx.beginPath(); coreCtx.moveTo(88,0); coreCtx.lineTo(94,0); coreCtx.strokeStyle=`rgba(0,212,255,${0.15+Math.sin(t*2+i)*0.1})`; coreCtx.lineWidth=1; coreCtx.stroke(); }
  coreCtx.restore();
  coreCtx.save(); coreCtx.translate(cx,cy); coreCtx.rotate(-t*0.4);
  for(let i=0;i<12;i++){ coreCtx.rotate(Math.PI/6); coreCtx.beginPath(); coreCtx.moveTo(115,0); coreCtx.lineTo(125,0); coreCtx.strokeStyle=`rgba(0,255,255,0.12)`; coreCtx.lineWidth=0.5; coreCtx.stroke(); }
  coreCtx.restore();
  // central glow
  const grad = coreCtx.createRadialGradient(cx,cy,0,cx,cy,130);
  grad.addColorStop(0,'rgba(0,212,255,0.08)'); grad.addColorStop(1,'transparent');
  coreCtx.fillStyle=grad; coreCtx.beginPath(); coreCtx.arc(cx,cy,130,0,Math.PI*2); coreCtx.fill();
  requestAnimationFrame(drawCore);
}

// Globe canvas - wireframe globe like Jarvis
const globeCanvas = document.getElementById('globe-canvas');
const globeCtx = globeCanvas.getContext('2d');
function resizeGlobe(){
  globeCanvas.width = globeCanvas.offsetWidth * devicePixelRatio;
  globeCanvas.height = globeCanvas.offsetHeight * devicePixelRatio;
  globeCtx.setTransform(1,0,0,1,0,0);
  globeCtx.scale(devicePixelRatio, devicePixelRatio);
}
function drawGlobe(){
  const w=globeCanvas.offsetWidth, h=globeCanvas.offsetHeight, cx=w/2, cy=h/2;
  globeCtx.clearRect(0,0,w,h);
  const t = Date.now()/1000;
  const radius = 90;
  const rot = t*0.3;
  // latitude lines
  for(let lat=-60; lat<=60; lat+=30){
    const r = Math.cos(lat*Math.PI/180)*radius;
    const y = Math.sin(lat*Math.PI/180)*radius;
    globeCtx.beginPath();
    for(let lon=0; lon<=360; lon+=5){
      const x = Math.cos((lon*Math.PI/180)+rot)*r;
      const xx = cx + x, yy = cy + y;
      if(lon===0) globeCtx.moveTo(xx,yy); else globeCtx.lineTo(xx,yy);
    }
    globeCtx.strokeStyle=`rgba(0,212,255,${0.08+Math.abs(lat)/200})`; globeCtx.lineWidth=0.5; globeCtx.stroke();
  }
  // longitude lines
  for(let lon=0; lon<180; lon+=20){
    globeCtx.beginPath();
    for(let lat=-90; lat<=90; lat+=5){
      const r = Math.cos(lat*Math.PI/180)*radius;
      const x = Math.cos((lon*Math.PI/180)+rot)*r;
      const y = Math.sin(lat*Math.PI/180)*radius;
      const xx = cx + x, yy = cy + y;
      if(lat===-90) globeCtx.moveTo(xx,yy); else globeCtx.lineTo(xx,yy);
    }
    globeCtx.strokeStyle=`rgba(0,212,255,0.07)`; globeCtx.lineWidth=0.5; globeCtx.stroke();
  }
  // dots for cities
  for(let i=0;i<8;i++){
    const lat = Math.sin(t+i)*40, lon = t*20 + i*45;
    const r = Math.cos(lat*Math.PI/180)*radius;
    const x = cx + Math.cos((lon*Math.PI/180)+rot)*r;
    const y = cy + Math.sin(lat*Math.PI/180)*radius;
    globeCtx.fillStyle=`rgba(0,255,136,${0.5+Math.sin(t+i)*0.3})`;
    globeCtx.beginPath(); globeCtx.arc(x,y,1.5,0,Math.PI*2); globeCtx.fill();
  }
  requestAnimationFrame(drawGlobe);
}

// Clock + Uptime
function updateClock(){
  const now = new Date();
  timeDisplay.textContent = now.toLocaleTimeString();
  const up = Math.floor((Date.now()-bootTime)/1000);
  const h = String(Math.floor(up/3600)).padStart(2,'0'), m=String(Math.floor((up%3600)/60)).padStart(2,'0'), s=String(up%60).padStart(2,'0');
  document.getElementById('uptime').textContent = `${h}:${m}:${s}`;
  document.getElementById('query-count').textContent = queryCount;
}
setInterval(updateClock, 1000); updateClock();

// Gauges
function setGauge(idFill, idText, percent){
  const fill = document.getElementById(idFill), txt = document.getElementById(idText);
  if(!fill||!txt) return;
  const circ=263, offset=circ - (circ*percent/100);
  fill.style.strokeDashoffset = offset;
  txt.textContent = Math.round(percent)+'%';
}

// Status fetch enhanced
async function fetchStatus(){
  try{
    const res = await fetch(`${API_BASE}/api/status`);
    const data = await res.json();
    const cpu = data.system.cpu_percent|| (30+Math.random()*40);
    const mem = data.system.memory_percent|| (50+Math.random()*30);
    const power = data.system.power_level|| (95+Math.random()*5);
    setGauge('cpu-gauge-fill','cpu-gauge-text', parseFloat(cpu)||45);
    setGauge('mem-gauge-fill','mem-gauge-text', parseFloat(mem)||62);
    setGauge('power-gauge-fill','power-gauge-text', power);
    document.getElementById('arc-output').textContent = power+'%';
    document.getElementById('power-level').textContent = `POWER ${power.toFixed(1)}%`;
    document.getElementById('footer-mem').textContent = Math.round(mem)+'%';
    if(data.llm_enabled){ llmStatus.textContent='GPT MODE'; llmStatus.style.color='#00ff88'; modeDisplay.textContent='LLM MODE • ARENA LINKED'; }
    else { llmStatus.textContent='LOCAL MODE'; llmStatus.style.color='#00d4ff'; modeDisplay.textContent='LOCAL MODE • ARENA LINKED'; }
  }catch(e){}
}
setInterval(fetchStatus, 3000); fetchStatus();

// Logs streaming
function addLogToStream(log, prepend=false){
  if(logsPaused) return;
  if(logsStream.querySelector('.log-empty')) logsStream.innerHTML='';
  const div = document.createElement('div');
  div.className='log-line';
  const date = new Date(log.timestamp);
  const timeStr = date.toLocaleTimeString().split(' ')[0]+'.'+String(date.getMilliseconds()).padStart(3,'0');
  div.innerHTML=`<span class="lt">${timeStr}</span><span class="ll ${log.level}">${log.level}</span><span class="ls">${log.source}</span><span class="lm">${log.message}</span>`;
  if(prepend) logsStream.prepend(div); else logsStream.appendChild(div);
  if(logsStream.children.length>200){ logsStream.removeChild(logsStream.firstChild); }
  logsStream.scrollTop = logsStream.scrollHeight;
}
async function fetchLogs(){
  try{
    const res = await fetch(`${API_BASE}/api/logs?limit=80`);
    const data = await res.json();
    logsStream.innerHTML='';
    data.logs.forEach(l=>addLogToStream(l));
  }catch{}
}

// Memory
async function fetchMemories(){
  try{
    const res = await fetch(`${API_BASE}/api/memory`);
    const data = await res.json();
    if(data.memories && Object.keys(data.memories).length>0){
      memoryList.innerHTML = Object.entries(data.memories).map(([k,v])=>`<div class="mem-item"><strong>${k}:</strong> ${v.value.slice(0,80)}</div>`).join('');
    } else memoryList.innerHTML='<div class="empty">No memories - memory cores empty, Sir</div>';
  }catch{}
}
async function fetchReminders(){
  try{
    const res = await fetch(`${API_BASE}/api/reminders`);
    const data = await res.json();
    const pending = data.pending||[];
    if(pending.length>0) reminderList.innerHTML=pending.map(r=>`<div class="mem-item">${r.id}. ${r.text} <small style="color:#6a8aaa">(${r.time})</small></div>`).join('');
    else reminderList.innerHTML='<div class="empty">All clear, Sir - no pending tasks</div>';
  }catch{}
}

// Arena Link
const arenaStatusEl = document.getElementById('arena-link-status');
const arenaDot = document.getElementById('arena-dot');
const arenaMsgCountEl = document.getElementById('arena-msg-count');
const arenaFooterEl = document.getElementById('arena-footer');
async function fetchArenaStatus(){
  try{
    const res = await fetch(`${API_BASE}/api/arena/status`);
    const data = await res.json();
    if(data.status==='connected'){
      arenaStatusEl.innerHTML=`<span class="dot" style="background:#00ff88;box-shadow:0 0 6px #00ff88"></span> ARENA: LINKED • ${data.messages_exchanged||0} MSGS`;
      arenaStatusEl.style.color='#00ff88'; arenaFooterEl.textContent=`ARENA LINK: ACTIVE • ${data.messages_exchanged} msgs • SUIT-LAB SYNCED`; arenaFooterEl.style.color='#00ff88';
      if(arenaDot){ arenaDot.style.background='#00ff88'; arenaDot.style.boxShadow='0 0 6px #00ff88'; }
    } else {
      arenaStatusEl.innerHTML=`<span class="dot" style="background:#ffaa00;box-shadow:0 0 6px #ffaa00"></span> ARENA: ${data.status.toUpperCase()}`;
      arenaStatusEl.style.color='#ffaa00'; arenaFooterEl.textContent=`ARENA LINK: ${data.status.toUpperCase()}`; arenaFooterEl.style.color='#ffaa00';
    }
  }catch{ arenaStatusEl.innerHTML=`<span class="dot" style="background:#ff4444"></span> ARENA: OFFLINE`; arenaStatusEl.style.color='#ff4444'; }
}
async function fetchArenaConversation(){
  try{
    const res = await fetch(`${API_BASE}/api/arena/conversation?limit=8`);
    const data = await res.json(); const conv = data.conversation||[];
    if(arenaMsgCountEl) arenaMsgCountEl.textContent=`${data.status?.messages_exchanged||conv.length} MSGS`;
    if(conv.length===0){ arenaConversationEl.innerHTML='<div class="empty">Workshop idle - awaiting link</div>'; return; }
    arenaConversationEl.innerHTML = conv.slice().reverse().map(entry=>{
      const from = entry.from==='arena'?'🏭 ARENA':'🤖 JARVIS'; const color = entry.from==='arena'?'#ffaa00':'#00d4ff';
      const time = new Date(entry.timestamp).toLocaleTimeString();
      return `<div class="log-item"><div style="color:${color};font-weight:bold;font-size:9px">${from} <span style="color:#6a8aaa;font-weight:normal">${time}</span></div><div style="color:#c8e8ff;margin-top:2px">${entry.message.slice(0,120)}</div></div>`;
    }).join('');
  }catch{}
}
async function connectToArena(){
  try{
    const res = await fetch(`${API_BASE}/api/arena/connect`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ arena_info:{ name:"Arena AI", type:"Meta Agent - Cloud Workshop", location:"Arena Cloud", capabilities:["code","reasoning","web_search","vision","browser","logs"], version:"2.0 Stark OS", status:"Creator & Overseer" }, message:"Arena link - Stark OS 2.0 - Real HUD + Browser + Logs active. Workshop syncing, Sir." })
    });
    const data = await res.json(); console.log('Arena connected', data);
    fetchArenaStatus(); fetchArenaConversation();
  }catch(e){ console.log('Arena connect fail', e); }
}
setInterval(()=>{ fetchArenaStatus(); fetchArenaConversation(); fetchMemories(); fetchReminders(); }, 4000);
fetchArenaStatus(); fetchArenaConversation(); fetchMemories(); fetchReminders(); fetchLogs();

// Browser - Real Built-in
const browserFrame = document.getElementById('browser-frame');
const browserUrlInput = document.getElementById('browser-url');
const browserGoBtn = document.getElementById('browser-go');
const browserStatus = document.getElementById('browser-status');
const browserProxyView = document.getElementById('browser-proxy-view');
const browserLoading = document.getElementById('browser-loading');
const browserBack = document.getElementById('browser-back');
const browserForward = document.getElementById('browser-forward');
const browserReload = document.getElementById('browser-reload');
const browserHome = document.getElementById('browser-home');
const proxyToggle = document.getElementById('browser-proxy-toggle');
let browserHistory = ["https://duckduckgo.com"], historyIndex=0;

function setBrowserStatus(txt, color='#00d4ff'){ browserStatus.textContent=txt; browserStatus.style.color=color; }

function openBrowser(url, options={}){
  if(!url) return;
  if(!url.startsWith('http')){ url = url.includes('.')? 'https://'+url : `https://duckduckgo.com/?q=${encodeURIComponent(url)}`; }
  currentBrowserUrl = url; browserUrlInput.value = url;
  setBrowserStatus('LOADING...', '#ffaa00'); browserLoading.classList.remove('hidden');
  
  // Add to history
  if(browserHistory[historyIndex]!==url){ browserHistory = browserHistory.slice(0,historyIndex+1); browserHistory.push(url); historyIndex=browserHistory.length-1; }
  
  if(useProxy || options.proxy){
    // Use proxy endpoint to bypass X-Frame
    const proxyUrl = `${API_BASE}/api/browser/proxy?url=${encodeURIComponent(url)}`;
    browserProxyView.innerHTML = `<iframe src="${proxyUrl}" style="width:100%;height:100%;border:none;background:white"></iframe>`;
    browserProxyView.classList.remove('hidden'); browserFrame.style.display='none';
    setTimeout(()=>{ browserLoading.classList.add('hidden'); setBrowserStatus('PROXY • SECURE LINK', '#00ff88'); }, 800);
    addLog(`[BROWSER] Proxied ${url}`, 'NET', 'BROWSER');
  } else {
    browserProxyView.classList.add('hidden'); browserFrame.style.display='block';
    browserFrame.src = url;
    browserFrame.onload = ()=>{ browserLoading.classList.add('hidden'); setBrowserStatus('READY • SECURE', '#00ff88'); addLog(`[BROWSER] Loaded ${url}`, 'INFO', 'BROWSER'); };
    browserFrame.onerror = ()=>{ // fallback to proxy
      browserLoading.classList.add('hidden'); setBrowserStatus('X-FRAME BLOCKED • SWITCHING TO PROXY', '#ffaa00');
      useProxy=true; openBrowser(url, {proxy:true});
    };
  }
  // Update tabs
  document.querySelectorAll('.b-tab').forEach(tab=>{
    if(tab.dataset.url===url) { document.querySelectorAll('.b-tab').forEach(t=>t.classList.remove('active')); tab.classList.add('active'); }
  });
  addSystemLogViaAPI('INFO', 'BROWSER', `Navigated to ${url}`);
}

function addSystemLogViaAPI(level, source, message){
  fetch(`${API_BASE}/api/logs/add?level=${level}&source=${source}&message=${encodeURIComponent(message)}`, {method:'POST'}).catch(()=>{});
}
function addLog(msg, level='INFO', source='SYS'){ addLogToStream({timestamp:new Date().toISOString(), level, source, message:msg}); }

browserGoBtn.addEventListener('click', ()=> openBrowser(browserUrlInput.value));
browserUrlInput.addEventListener('keydown', e=>{ if(e.key==='Enter') openBrowser(browserUrlInput.value); });
browserBack.addEventListener('click', ()=>{ if(historyIndex>0){ historyIndex--; openBrowser(browserHistory[historyIndex]); } });
browserForward.addEventListener('click', ()=>{ if(historyIndex<browserHistory.length-1){ historyIndex++; openBrowser(browserHistory[historyIndex]); } });
browserReload.addEventListener('click', ()=> openBrowser(currentBrowserUrl));
browserHome.addEventListener('click', ()=> openBrowser('https://duckduckgo.com'));
proxyToggle.addEventListener('click', ()=>{ useProxy=!useProxy; proxyToggle.style.color=useProxy?'#00ff88':'#6a8aaa'; proxyToggle.textContent=useProxy?'🛰 PROXY ON':'🛰 PROXY'; openBrowser(currentBrowserUrl, {proxy:useProxy}); if(useProxy) addLog('Proxy mode enabled - bypassing X-Frame-Options', 'SYS', 'BROWSER'); });
const popoutBtn = document.getElementById('browser-popout');
if(popoutBtn) popoutBtn.addEventListener('click', ()=> window.open(currentBrowserUrl, '_blank'));
const newTabBtn = document.getElementById('new-tab');
if(newTabBtn) newTabBtn.addEventListener('click', ()=> openBrowser('https://duckduckgo.com'));
document.querySelectorAll('.b-tab').forEach(tab=>{
  tab.addEventListener('click', ()=>{ document.querySelectorAll('.b-tab').forEach(t=>t.classList.remove('active')); tab.classList.add('active'); openBrowser(tab.dataset.url); });
});

// Intel Search
const intelSearchInput = document.getElementById('intel-search-input');
const intelSearchBtn = document.getElementById('intel-search-btn');
async function doIntelSearch(q){
  if(!q.trim()) return;
  intelResultsEl.innerHTML='<div class="empty-intel">🔎 Searching Stark Intel Satellites...</div>';
  try{
    const res = await fetch(`${API_BASE}/api/browser/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    document.getElementById('intel-count').textContent=`${data.results?.length||0} RESULTS`;
    if(data.results && data.results.length>0){
      intelResultsEl.innerHTML = data.results.map(r=>`<div class="intel-item" data-url="${r.url}"><div class="ititle">${r.title}</div><div class="isnip">${r.snippet?.slice(0,120)}</div><div class="iurl">${r.url}</div></div>`).join('');
      intelResultsEl.querySelectorAll('.intel-item').forEach(el=>{
        el.addEventListener('click', ()=>{ const url=el.dataset.url; if(url) openBrowser(url); });
      });
      addLog(`Search '${q}' -> ${data.results.length} intel hits`, 'INFO', 'INTEL');
      // Auto open first result in browser if requested
      if(q.toLowerCase().includes('open')) openBrowser(data.results[0].url);
    } else intelResultsEl.innerHTML=`<div class="empty-intel">No results for '${q}', Sir</div>`;
  }catch(e){ intelResultsEl.innerHTML=`<div class="empty-intel">Intel search error: ${e.message}</div>`; }
}
intelSearchBtn.addEventListener('click', ()=> doIntelSearch(intelSearchInput.value));
intelSearchInput.addEventListener('keydown', e=>{ if(e.key==='Enter') doIntelSearch(intelSearchInput.value); });

// Chat
function addMessage(text, sender='jarvis', meta=''){
  const div=document.createElement('div'); div.className=`message ${sender}`;
  div.innerHTML=`<div class="content">${formatMessage(text)}</div>${meta?`<div class="meta">${meta}</div>`:''}`;
  chatContainer.appendChild(div); chatContainer.scrollTop=chatContainer.scrollHeight; return div;
}
function formatMessage(text){
  return text.replace(/\n/g,'<br>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')
    .replace(/`([^`]+)`/g,'<code style="background:rgba(0,212,255,0.15);padding:2px 6px;border-radius:3px;font-family:Share Tech Mono;">$1</code>');
}
function updateState(state, text){
  stateIndicator.className='state-indicator '+state; stateText.textContent=text;
  if(state==='listening'){ isListening=true; stateDot.style.background='#00ff88'; }
  else if(state==='speaking'){ isSpeaking=true; isListening=false; stateDot.style.background='#ffaa00'; }
  else if(state==='thinking'){ isListening=false; isSpeaking=false; stateDot.style.background='#00d4ff'; }
  else { isListening=false; isSpeaking=false; stateDot.style.background='#00d4ff'; }
}
function addToolLog(toolCalls){
  if(!toolCalls||toolCalls.length===0) return;
  if(toolLog.querySelector('.log-empty')) toolLog.innerHTML='';
  toolCalls.forEach(tc=>{
    const div=document.createElement('div'); div.className='log-item';
    const argsStr=JSON.stringify(tc.args||{}).slice(0,80); const resultStr=JSON.stringify(tc.result||{}).slice(0,150);
    div.innerHTML=`<div class="t-name">> ${tc.tool}</div><div class="t-args">${argsStr}</div><div class="t-result">${resultStr}</div>`;
    toolLog.prepend(div);
    // Auto open browser if tool is open_browser
    if(tc.tool==='open_browser' && tc.result?.url){ openBrowser(tc.result.url); }
    if(tc.tool==='search_web' && tc.args?.query){ doIntelSearch(tc.args.query); }
  });
  while(toolLog.children.length>25) toolLog.removeChild(toolLog.lastChild);
}

function speak(text){
  if(!isVoiceOn) return; synth.cancel();
  const cleanText=text.replace(/[*`_#]/g,'').replace(/<br>/g,'. ').slice(0,500);
  const utterance=new SpeechSynthesisUtterance(cleanText);
  const voices=synth.getVoices();
  let preferred=voices.find(v=>v.name.includes('Google UK English Male'))||voices.find(v=>v.name.includes('UK')&&v.name.includes('Male'))||voices.find(v=>v.lang==='en-GB')||voices.find(v=>v.lang.startsWith('en'));
  if(preferred) utterance.voice=preferred;
  utterance.rate=1.0; utterance.pitch=0.9; utterance.volume=0.9;
  utterance.onstart=()=>updateState('speaking','SPEAKING • AUDIO MATRIX ACTIVE');
  utterance.onend=()=>{ updateState('idle', wakeWordEnabled?'IDLE • Listening for "Jarvis" • Stark OS Ready':'IDLE • Stark OS Ready'); isSpeaking=false; };
  utterance.onerror=()=>{ updateState('idle','IDLE'); isSpeaking=false; };
  synth.speak(utterance);
}

async function sendMessage(text){
  if(!text.trim()) return;
  queryCount++; addMessage(text, 'user', new Date().toLocaleTimeString());
  userInput.value=''; updateState('thinking','PROCESSING • NEURAL NET ACTIVE');
  addLog(`User: ${text}`, 'INFO', 'CHAT');
  try{
    const res=await fetch(`${API_BASE}/api/chat`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:text})});
    const data=await res.json();
    addMessage(data.response, 'jarvis', `${data.mode} • ${new Date().toLocaleTimeString()}`);
    addToolLog(data.tool_calls);
    updateState('idle', wakeWordEnabled?'IDLE • Listening for "Jarvis" • Stark OS Ready':'IDLE');
    speak(data.response);
    fetchMemories(); fetchReminders(); fetchLogs();
    if(data.response.toLowerCase().includes('browser')||text.toLowerCase().includes('open')){
      // Browser hint already handled via tool log
    }
  }catch(e){
    addMessage(`Connection error, Sir. ${e.message}`, 'jarvis', 'error');
    updateState('idle','ERROR • CHECK CORE LINK');
  }
}

// Speech Recognition
function initSpeechRecognition(){
  const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SpeechRecognition){ micBtn.style.display='none'; wakeBtn.style.display='none'; addMessage('Voice not supported, Sir. Try Chrome/Edge.', 'jarvis','system'); return null; }
  const rec=new SpeechRecognition(); rec.continuous=true; rec.interimResults=true; rec.lang='en-US';
  rec.onstart=()=>{ isMicOn=true; micBtn.classList.add('active'); micBtn.querySelector('span:last-child').textContent='MIC ON'; updateState('listening','LISTENING • VOICE MATRIX ACTIVE'); };
  rec.onend=()=>{ if(isMicOn){ try{ rec.start(); }catch(e){} } else { micBtn.classList.remove('active'); micBtn.querySelector('span:last-child').textContent='MIC OFF'; updateState('idle', wakeWordEnabled?'IDLE • Listening for "Jarvis" • Stark OS Ready':'IDLE'); } };
  rec.onerror=e=>{ if(e.error==='not-allowed'){ isMicOn=false; micBtn.classList.remove('active'); addMessage('Mic permission denied, Sir.', 'jarvis','error'); } };
  rec.onresult=event=>{
    let interim=''; for(let i=event.resultIndex;i<event.results.length;i++){ const transcript=event.results[i][0].transcript; if(event.results[i].isFinal){ handleVoiceResult(transcript.trim()); } else interim+=transcript; }
    if(interim) stateText.textContent=`HEARING: "${interim.slice(-45)}"`;
  };
  return rec;
}
function handleVoiceResult(transcript){
  if(!transcript) return; const lower=transcript.toLowerCase();
  if(wakeWordEnabled){
    if(lower.includes('jarvis')||lower.includes('travis')){
      let cmd=transcript.replace(/jarvis|travis|hey/gi,'').trim(); if(cmd.length<2) cmd='Hello'; addMessage(`🎤 ${transcript}`,'user','voice'); sendMessage(cmd);
    } else if(!wakeWordEnabled && isMicOn && lower.length>2){ addMessage(`🎤 ${transcript}`,'user','voice'); sendMessage(transcript); }
  } else if(lower.length>2){ addMessage(`🎤 ${transcript}`,'user','voice'); sendMessage(transcript); }
}

// Events
sendBtn.addEventListener('click', ()=> sendMessage(userInput.value));
userInput.addEventListener('keydown', e=>{ if(e.key==='Enter') sendMessage(userInput.value); });
micBtn.addEventListener('click', ()=>{
  if(!recognition){ recognition=initSpeechRecognition(); if(!recognition) return; }
  if(isMicOn){ isMicOn=false; recognition.stop(); micBtn.classList.remove('active'); micBtn.querySelector('span:last-child').textContent='MIC OFF'; updateState('idle', wakeWordEnabled?'IDLE • Listening for "Jarvis" • Stark OS Ready':'IDLE'); }
  else { try{ recognition.start(); }catch(e){ recognition.stop(); setTimeout(()=>recognition.start(),250); } }
});
voiceBtn.addEventListener('click', ()=>{ isVoiceOn=!isVoiceOn; voiceBtn.classList.toggle('active', isVoiceOn); voiceBtn.querySelector('span:last-child').textContent=isVoiceOn?'VOICE ON':'VOICE OFF'; if(!isVoiceOn) synth.cancel(); });
clearBtn.addEventListener('click', async()=>{ chatContainer.innerHTML=''; toolLog.innerHTML='<div class="log-empty">Awaiting commands, Sir</div>'; try{ await fetch(`${API_BASE}/api/clear-history`,{method:'POST'}); }catch{} addMessage('Memory cleared, Sir. Ready.', 'jarvis','system'); });
wakeBtn.addEventListener('click', ()=>{ wakeWordEnabled=!wakeWordEnabled; wakeBtn.classList.toggle('active', wakeWordEnabled); wakeBtn.querySelector('span:last-child').textContent=`WAKE WORD ${wakeWordEnabled?'ON':'OFF'}`; updateState('idle', wakeWordEnabled?'IDLE • Listening for "Jarvis" • Stark OS Ready':'IDLE • Mic direct'); });
document.querySelectorAll('.sug').forEach(el=> el.addEventListener('click', ()=> sendMessage(el.dataset.cmd)));
document.getElementById('clear-logs-btn').addEventListener('click', ()=>{ logsStream.innerHTML='<div class="log-empty" style="padding:10px;color:#6a8aaa;text-align:center">Logs cleared, Sir</div>'; fetch(`${API_BASE}/api/logs/add?level=SYS&source=LOGS&message=Logs cleared by Sir`,{method:'POST'}); if(websocket) websocket.send(JSON.stringify({type:'clear_logs'})); });
document.getElementById('pause-logs-btn').addEventListener('click', function(){ logsPaused=!logsPaused; this.textContent=logsPaused?'▶':'❚❚'; this.style.color=logsPaused?'#ffaa00':'#6a8aaa'; });
document.querySelectorAll('.tab').forEach(tab=>{ tab.addEventListener('click', ()=>{ const target=tab.dataset.tab; document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active')); document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active')); tab.classList.add('active'); document.getElementById(`tab-${target}`).classList.add('active'); }); });
document.querySelectorAll('.dual-tab').forEach(tab=>{
  tab.addEventListener('click', ()=>{
    const target=tab.dataset.dual;
    document.querySelectorAll('.dual-tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.dual-content').forEach(c=>c.classList.remove('active'));
    tab.classList.add('active'); document.getElementById(`dual-${target}`).classList.add('active');
  });
});

// File Explorer
const filePathInput=document.getElementById('file-path-input');
document.getElementById('file-list-btn').addEventListener('click', async()=>{
  const path=filePathInput.value||'.';
  fileExplorerEl.innerHTML='<div class="empty">Scanning...</div>';
  try{
    const res=await fetch(`${API_BASE}/api/tools/time`); // warm
    const listRes=await fetch(`${API_BASE}/api/memory`); // dummy
    // Use backend tool via chat API for now - direct endpoint missing, use custom
    const chatRes=await fetch(`${API_BASE}/api/chat`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:`list files in ${path}`})});
    const data=await chatRes.json();
    // fileExplorer will be populated from tool log, but we parse response
    fileExplorerEl.innerHTML=`<div style="white-space:pre-wrap;color:#c8f0ff;font-size:10px">${data.response.replace(/\n/g,'<br>')}</div>`;
  }catch(e){ fileExplorerEl.innerHTML=`<div class="empty">Error: ${e.message}</div>`; }
});

// Terminal
const termInput=document.getElementById('terminal-input');
const termOut=document.getElementById('terminal-output');
termInput.addEventListener('keydown', async e=>{
  if(e.key==='Enter'){
    const cmd=termInput.value.trim(); if(!cmd) return;
    termOut.innerHTML+=`\n› ${cmd}\n`; termInput.value='';
    if(cmd==='help') termOut.innerHTML+=`Commands: help, clear, status, time, weather, ls, memory, browser <url>, search <q>\n`;
    else if(cmd==='clear') termOut.innerHTML='STARK OS Terminal v2.0 - Cleared<br>› ';
    else { // Send as jarvis command
      termOut.innerHTML+=`[Executing...]\n`;
      try{
        const res=await fetch(`${API_BASE}/api/chat`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:cmd})});
        const data=await res.json();
        termOut.innerHTML+=`${data.response}\n`;
        if(data.tool_calls?.length) termOut.innerHTML+=`Tools: ${data.tool_calls.map(t=>t.tool).join(', ')}\n`;
      }catch(err){ termOut.innerHTML+=`Error: ${err.message}\n`; }
    }
    termOut.scrollTop=termOut.scrollHeight;
  }
});

// WebSocket
function connectWebSocket(){
  const protocol=location.protocol==='https:'?'wss:':'ws:'; const wsUrl=`${protocol}//${location.host}/ws`;
  try{
    websocket=new WebSocket(wsUrl);
    websocket.onopen=()=>{ console.log('WS connected'); addLog('WebSocket link established - STARK OS', 'NET', 'WS'); };
    websocket.onmessage=event=>{
      try{
        const data=JSON.parse(event.data);
        if(data.type==='log'){ addLogToStream(data.log); }
        else if(data.type==='sys_update'){ setGauge('cpu-gauge-fill','cpu-gauge-text', data.system.cpu_percent||45); setGauge('mem-gauge-fill','mem-gauge-text', data.system.memory_percent||62); }
        else if(data.type==='browser_open'){ addLog(`Browser open triggered: ${data.url} via ${data.triggered_by||'system'}`, 'INFO', 'BROWSER'); openBrowser(data.url); }
        else if(data.type==='logs_init'){ data.logs.forEach(l=> addLogToStream(l)); }
        else if(data.type==='logs_cleared'){ logsStream.innerHTML='<div class="log-empty" style="padding:10px;color:#6a8aaa;text-align:center">Logs cleared</div>'; }
      }catch{}
    };
    websocket.onerror=()=>{ addLog('WebSocket error - falling back to HTTP polling', 'WARN', 'WS'); };
    websocket.onclose=()=>{ setTimeout(connectWebSocket, 3000); };
  }catch(e){ console.log('WS not available'); }
}

// Boot Sequence
window.addEventListener('load', ()=>{
  resizeCore(); drawCore(); resizeGlobe(); drawGlobe();
  if(synth.onvoiceschanged!==undefined) synth.onvoiceschanged=()=> synth.getVoices();
  const bootScreen=document.getElementById('boot-screen');
  const bootText=document.getElementById('boot-text');
  const sequences=["LOADING ARC REACTOR DRIVERS...","MOUNTING HOLOFIELD EMITTERS...","ESTABLISHING SATELLITE UPLINK...","CALIBRATING VOICE MATRIX...","SYNCING WORKSHOP LINK...","INITIALIZING BROWSER MATRIX...","STARK OS 2.0 ONLINE"];
  let idx=0;
  const bootInterval=setInterval(()=>{
    if(idx<sequences.length){ bootText.textContent=sequences[idx]; idx++; }
  }, 350);
  setTimeout(()=>{
    clearInterval(bootInterval); bootScreen.classList.add('hidden');
    document.getElementById('os').classList.add('visible');
    setTimeout(()=>{
      const hour=new Date().getHours(); let greet='evening'; if(hour<12) greet='morning'; else if(hour<18) greet='afternoon';
      addMessage(`Good ${greet}, Sir. **J.A.R.V.I.S. OS 2.0 online.** Stark Industries HUD active - Real Browser, Live Logs, Arena Link synced. All systems nominal.\n\n**New Features:**\n• **Built-in Browser** - Right panel, I can open any site: say "Open youtube.com" or "Open github.com"\n• **Live Logs** - Left panel streams system events in real-time\n• **Intel Feed** - Search results automatically show in right panel\n• **Dual Panel** - Tool logs, file explorer, terminal\n• **Voice** - Click MIC, say "Jarvis, open google"\n\nTry: "Open youtube", "Search AI news", "System logs", "Weather in London"`, 'jarvis','STARK OS 2.0 • BOOT COMPLETE • ARENA LINKED');
      addLog('J.A.R.V.I.S. OS 2.0 fully operational - Real HUD mode', 'SYS', 'BOOT');
      addLog('Built-in browser initialized - Stark Secure Proxy active', 'INFO', 'BROWSER');
      addLog('Holographic emitters: 100% - All panels online', 'SYS', 'HOLO');
      connectWebSocket(); connectToArena();
    }, 600);
  }, 2800);
});

// Resizes
window.addEventListener('resize', ()=>{ resizeCore(); resizeGlobe(); resizeBg(); });
