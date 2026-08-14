/* =====================================================
   OMNI-PERSPECTIVE ENGINE — JavaScript
   Sage/Gold palette · Skeleton loading · Optimistic UI
   Staged progress · Confidence indicators · Why-not box
   ===================================================== */

/* ── Reduced-motion utility ── */
const prefersReducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ── NAV SCROLL STATE ── */
window.addEventListener('scroll', () => {
  document.getElementById('nav').classList.toggle('scrolled', window.scrollY > 20);
});

/* =====================================================
   ANIMATED HERO BACKGROUND CANVAS
   ===================================================== */
(function initHeroCanvas() {
  const container = document.getElementById('heroCanvas');
  if (!container) return;
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;';
  container.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  let W, H, nodes, frame;

  // Updated to peach/apricot/blue palette
  const COLORS = {
    node_sage:  'rgba(212,235,253,0.85)', // Baby blue
    node_gold:  'rgba(255,190,145,0.80)', // Peach
    node_dim:   'rgba(212,235,253,0.15)', // Dimmed blue
    edge_sage:  'rgba(212,235,253,0.10)',
    edge_contra:'rgba(255,138,122,0.40)', // Red conflict
  };

  function resize() {
    W = canvas.width  = container.offsetWidth;
    H = canvas.height = container.offsetHeight;
    buildNodes();
  }
  function rand(a, b) { return a + Math.random() * (b - a); }
  function buildNodes() {
    nodes = Array.from({ length: 55 }, (_, i) => ({
      x: rand(0, W), y: rand(0, H),
      vx: rand(-0.22, 0.22), vy: rand(-0.18, 0.18),
      r: rand(2, 5.5),
      type: i < 4 ? 'gold' : (i < 18 ? 'sage' : 'dim'),
      pulse: rand(0, Math.PI * 2),
      pulseSpeed: rand(0.012, 0.028),
    }));
  }
  function drawFrame(t) {
    ctx.clearRect(0, 0, W, H);
    for (const n of nodes) {
      n.x += n.vx; n.y += n.vy;
      if (n.x < -20) n.x = W + 20; if (n.x > W + 20) n.x = -20;
      if (n.y < -20) n.y = H + 20; if (n.y > H + 20) n.y = -20;
      n.pulse += n.pulseSpeed;
    }
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.sqrt(dx*dx + dy*dy);
        if (d > 160) continue;
        const isContra = a.type === 'gold' || b.type === 'gold';
        ctx.beginPath();
        ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = isContra ? COLORS.edge_contra : COLORS.edge_sage;
        ctx.lineWidth = isContra ? 1.5 : 0.8;
        ctx.globalAlpha = 1 - d / 160;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }
    for (const n of nodes) {
      const glow = 0.5 + 0.5 * Math.sin(n.pulse);
      if (n.type !== 'dim') {
        const gradR = n.r * (3 + glow * 2);
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, gradR);
        grad.addColorStop(0, n.type === 'gold' ? `rgba(255,190,145,${0.22*glow})` : `rgba(212,235,253,${0.18*glow})`);
        grad.addColorStop(1, 'transparent');
        ctx.beginPath(); ctx.arc(n.x, n.y, gradR, 0, Math.PI*2);
        ctx.fillStyle = grad; ctx.fill();
      }
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI*2);
      ctx.fillStyle = n.type==='gold' ? COLORS.node_gold : (n.type==='sage' ? COLORS.node_sage : COLORS.node_dim);
      ctx.fill();
    }
    if (!prefersReducedMotion()) frame = requestAnimationFrame(drawFrame);
  }
  resize();
  window.addEventListener('resize', resize);
  requestAnimationFrame(drawFrame);
})();

/* =====================================================
   HERO LIVE DEMO — live contradiction demonstration
   ===================================================== */
(function buildHeroDemo() {
  const el = document.getElementById('heroDemoCanvas');
  if (!el) return;

  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;';
  el.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  let t = 0;

  const W = 600, H = 340;
  canvas.width = W; canvas.height = H;

  // Peach/apricot/blue palette for demo
  const SAGE   = '#D4EBFD'; // Baby blue
  const GOLD   = '#FFBE91'; // Peach
  const SAGEL  = '#FFDBBA'; // Apricot
  const RED    = '#FF8A7A'; // Red conflict
  const CREAM  = '#FFFDF0'; // Warm cream

  const entity = { x: 300, y: 170, r: 38, label: 'INFLATION\nRATE 2024' };
  const sources = [
    { x: 100, y: 90,  label: 'Reuters',   val: '3.2%', color: SAGEL },
    { x: 500, y: 80,  label: 'Bloomberg', val: '3.8%', color: RED   },
    { x: 90,  y: 270, label: 'FT',        val: '3.2%', color: SAGE  },
    { x: 500, y: 270, label: 'AP',        val: '3.9%', color: RED   },
  ];
  const contradictPairs = [[1, 3], [0, 3], [1, 2]];

  function rr(x, y, w, h, r, fill, stroke) {
    ctx.beginPath();
    ctx.moveTo(x+r, y); ctx.lineTo(x+w-r, y); ctx.quadraticCurveTo(x+w, y, x+w, y+r);
    ctx.lineTo(x+w, y+h-r); ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
    ctx.lineTo(x+r, y+h); ctx.quadraticCurveTo(x, y+h, x, y+h-r);
    ctx.lineTo(x, y+r); ctx.quadraticCurveTo(x, y, x+r, y); ctx.closePath();
    if (fill)  { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke){ ctx.strokeStyle = stroke; ctx.lineWidth = 1.5; ctx.stroke(); }
  }

  function drawLoop() {
    if (prefersReducedMotion()) {
      // Static frame for reduced motion
      ctx.clearRect(0,0,W,H);
      for (const s of sources) {
        ctx.strokeStyle = SAGE + '40'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(entity.x, entity.y); ctx.stroke();
      }
      for (const [ai, bi] of contradictPairs) {
        const a = sources[ai], b = sources[bi];
        ctx.strokeStyle = RED + '80'; ctx.lineWidth = 2;
        ctx.setLineDash([6,6]);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        ctx.setLineDash([]);
      }
      // Draw entity
      ctx.beginPath(); ctx.arc(entity.x, entity.y, entity.r, 0, Math.PI*2);
      ctx.fillStyle = 'rgba(14,20,27,0.95)'; ctx.strokeStyle = SAGE + 'AA'; ctx.lineWidth = 2;
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = CREAM; ctx.font = 'bold 9px "Space Grotesk",sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      entity.label.split('\n').forEach((line, i) => ctx.fillText(line, entity.x, entity.y + (i - 0.5)*12));
      // Draw sources
      for (const s of sources) {
        rr(s.x-44, s.y-22, 88, 44, 8, 'rgba(14,20,27,0.95)', s.color + 'AA');
        ctx.fillStyle = s.color; ctx.font = 'bold 10px "Space Grotesk",sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(s.label, s.x, s.y - 8);
        ctx.fillStyle = CREAM; ctx.font = '600 14px "JetBrains Mono",monospace';
        ctx.fillText(s.val, s.x, s.y + 8);
      }
      return;
    }

    ctx.clearRect(0, 0, W, H);

    // Support edges (source → entity)
    for (const s of sources) {
      ctx.setLineDash([]);
      ctx.strokeStyle = SAGE + '22'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(entity.x, entity.y); ctx.stroke();
    }

    // Contradiction edges (animated dashed)
    ctx.save();
    for (const [ai, bi] of contradictPairs) {
      const a = sources[ai], b = sources[bi];
      const phase = t * 0.06;
      ctx.setLineDash([7, 7]);
      ctx.lineDashOffset = -phase;
      const pulse = 0.55 + 0.45 * Math.sin(t * 0.03 + ai);
      ctx.strokeStyle = `rgba(200,122,106,${0.5 + 0.4 * pulse})`;
      ctx.lineWidth = 1.8;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();

      // CONFLICT label
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      ctx.save();
      rr(mx-30, my-10, 60, 20, 5, `rgba(255,138,122,${0.12*pulse})`, `rgba(255,138,122,${0.5*pulse})`);
      ctx.fillStyle = RED; ctx.font = '600 8px "JetBrains Mono",monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.setLineDash([]);
      ctx.fillText('CONFLICT', mx, my);
      ctx.restore();
    }
    ctx.restore();

    // Center entity
    const ep = 0.5 + 0.5 * Math.sin(t * 0.018);
    const egrad = ctx.createRadialGradient(entity.x, entity.y, 0, entity.x, entity.y, entity.r * 2.5);
    egrad.addColorStop(0, `rgba(212,235,253,${0.12 * ep})`);
    egrad.addColorStop(1, 'transparent');
    ctx.beginPath(); ctx.arc(entity.x, entity.y, entity.r * 2.5, 0, Math.PI*2);
    ctx.fillStyle = egrad; ctx.fill();

    ctx.beginPath(); ctx.arc(entity.x, entity.y, entity.r, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(14,20,27,0.95)';
    ctx.strokeStyle = `rgba(212,235,253,${0.5 + 0.3*ep})`;
    ctx.lineWidth = 2; ctx.fill(); ctx.stroke();
    ctx.fillStyle = CREAM; ctx.font = 'bold 9px "Space Grotesk",sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    entity.label.split('\n').forEach((line, i) => ctx.fillText(line, entity.x, entity.y + (i - 0.5)*12));

    // Source nodes
    for (const s of sources) {
      rr(s.x-44, s.y-22, 88, 44, 8, 'rgba(14,20,27,0.95)', s.color + 'AA');
      ctx.setLineDash([]);
      ctx.fillStyle = s.color; ctx.font = 'bold 10px "Space Grotesk",sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(s.label, s.x, s.y - 8);
      ctx.fillStyle = CREAM; ctx.font = '600 14px "JetBrains Mono",monospace';
      ctx.fillText(s.val, s.x, s.y + 8);
    }

    // Status text
    const alpha = 0.6 + 0.4 * Math.sin(t * 0.022);
    ctx.fillStyle = `rgba(255,138,122,${alpha})`;
    ctx.font = '600 9px "JetBrains Mono",monospace';
    ctx.textAlign = 'center';
    ctx.fillText('3 ACTIVE CONTRADICTIONS DETECTED', 300, 320);

    t++;
    requestAnimationFrame(drawLoop);
  }
  requestAnimationFrame(drawLoop);
})();

/* =====================================================
   ARCHITECTURE DIAGRAM
   ===================================================== */
(function buildArchDiagram() {
  const el = document.getElementById('archDiagram');
  if (!el) return;

  const SAGE = '#FFDBBA', SAGEL = '#D4EBFD', GOLD = '#FFBE91',
        RED  = '#FF8A7A', CREAM = '#FFDBBA';

  const layers = [
    { label: 'INGESTION LAYER',            sub: 'Phase 1: APScheduler polling · Phase 2: Kafka topics', color: SAGEL,  single: true },
    { label: 'CHUNKING & METADATA SERVICE', sub: 'Semantic chunking · author, timestamp, sentiment, claimed scope', color: SAGE,   single: true },
    { label: 'EXTRACTION SERVICE (LLM)',   sub: 'Entities → Neo4j · Embeddings → Qdrant · Event log → SQLite', color: GOLD,   single: true },
    { label: 'FORK', color: null, fork: [
        { label: 'Qdrant',  sub: 'Vector Store', color: SAGEL },
        { label: 'Neo4j',   sub: 'Graph Store',  color: GOLD  },
    ]},
    { label: 'LANGGRAPH ORCHESTRATION',    sub: 'Vector Agent · CRAG Agent · Synthesizer · Contradiction Classifier', color: CREAM,  single: true },
    { label: 'FASTAPI + UVICORN',          sub: 'REST /query · WebSocket /ws/query · Static file serving', color: SAGE,   single: true },
    { label: 'FRONTEND (HTML/JS)',          sub: 'Hero demo · Graph visualizer · Source-tracing · Temporal slider', color: RED,    single: true },
  ];

  const arrow = `<div class="arch-arrow-down">↓</div>`;
  let html = '';
  for (const layer of layers) {
    if (layer.fork) {
      html += `<div class="arch-fork">`;
      for (const f of layer.fork) {
        html += `<div class="arch-box" style="border-color:${f.color}44;background:${f.color}0d;min-width:160px;">
          <h5 style="color:${f.color}">${f.label}</h5><p>${f.sub}</p></div>`;
      }
      html += `</div>`;
    } else {
      html += `<div class="arch-layer"><div class="arch-box" style="border-color:${layer.color}44;background:${layer.color}0d;width:100%;max-width:640px;">
        <h5 style="color:${layer.color}">${layer.label}</h5><p>${layer.sub}</p></div></div>`;
    }
    html += arrow;
  }
  el.innerHTML = html;
})();

/* =====================================================
   SCROLL REVEAL
   ===================================================== */
(function initReveal() {
  if (prefersReducedMotion()) return;
  const style = document.createElement('style');
  style.textContent = `
    .reveal { opacity: 0; transform: translateY(22px); transition: opacity 0.55s ease, transform 0.55s ease; }
    .reveal.visible { opacity: 1; transform: none; }
  `;
  document.head.appendChild(style);
  const sel = '.phase-card,.pipeline-node,.db-card,.fe-card,.build-step,.risk-card,.taxon,.arch-box';
  document.querySelectorAll(sel).forEach((el, i) => {
    el.classList.add('reveal');
    el.style.transitionDelay = `${(i % 6) * 0.065}s`;
  });
  const obs = new IntersectionObserver(
    entries => entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); } }),
    { threshold: 0.10 }
  );
  document.querySelectorAll('.reveal').forEach(el => obs.observe(el));
})();

/* =====================================================
   ACTIVE NAV LINK on scroll
   ===================================================== */
(function initActiveNav() {
  const sections = document.querySelectorAll('section[id]');
  const links    = document.querySelectorAll('.nav-links a');
  const style = document.createElement('style');
  style.textContent = `.nav-links a.active { color: var(--gold) !important; background: var(--gold-dim) !important; }`;
  document.head.appendChild(style);
  const obs = new IntersectionObserver(
    entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          links.forEach(l => l.classList.remove('active'));
          const lk = document.querySelector(`.nav-links a[href="#${e.target.id}"]`);
          if (lk) lk.classList.add('active');
        }
      });
    },
    { rootMargin: '-40% 0px -50% 0px' }
  );
  sections.forEach(s => obs.observe(s));
})();

/* =====================================================
   SECTION 4: LIVE QUERY ENGINE
   ===================================================== */
let globalContradictions = [];
let globalGraphData = { nodes: [], edges: [] };
let activeWebSocket = null;
let isClustered = false;
let graphZoomScale = 1.0;

/* ── Stage progress names ─ */
const STAGE_LABELS = [
  'Reading sources…',
  'Evaluating chunks…',
  'Mapping entities…',
  'Grouping claims…',
  'Checking conflicts…',
];

/* ── Preset query helper ─ */
function setPresetQuery(text) {
  const input = document.getElementById('queryInput');
  if (input) {
    input.value = text;
    const form = document.getElementById('queryForm');
    if (form) {
      if (typeof form.requestSubmit === 'function') form.requestSubmit();
      else handleQuerySubmit(new Event('submit'));
    }
  }
}

/* ── Stage progress control ─ */
function setStageActive(n) {
  for (let i = 1; i <= 5; i++) {
    const el = document.getElementById(`stage-${i}`);
    if (!el) continue;
    el.classList.remove('active', 'done');
    if (i < n) el.classList.add('done');
    else if (i === n) el.classList.add('active');
  }
}
function setAllStagesDone() {
  for (let i = 1; i <= 5; i++) {
    const el = document.getElementById(`stage-${i}`);
    if (el) { el.classList.remove('active'); el.classList.add('done'); }
  }
}
function resetStages() {
  for (let i = 1; i <= 5; i++) {
    const el = document.getElementById(`stage-${i}`);
    if (el) el.classList.remove('active', 'done');
  }
}

/* ── Match pipeline steps to stage index ─ */
function stepToStageIndex(stepText) {
  if (/vector agent/i.test(stepText))          return 1;
  if (/crag agent/i.test(stepText))            return 2;
  if (/graph agent/i.test(stepText))           return 3;
  if (/synthesizer/i.test(stepText))           return 4;
  if (/classifier/i.test(stepText))            return 5;
  return null;
}

/* ── Main query handler ─ */
/* ── Main query handler ─ */
async function handleQuerySubmit(event) {
  if (event && event.preventDefault) event.preventDefault();
  const input = document.getElementById('queryInput');
  const query = input ? input.value.trim() : '';
  if (!query) return;

  // ─ Optimistic UI commit ─
  const form = document.getElementById('queryForm');
  if (form) form.classList.add('committed');

  const searchBtnText = document.getElementById('searchBtnText');
  const btnSpinner = document.getElementById('btnSpinner');
  if (searchBtnText) searchBtnText.textContent = 'Analyzing…';
  if (btnSpinner) btnSpinner.style.display = 'inline-block';

  const progressWrap = document.getElementById('stageProgressWrap');
  if (progressWrap) progressWrap.classList.add('visible');
  resetStages();
  setStageActive(1);

  // Show & scroll to results section
  const resultsSection = document.getElementById('live-results-section');
  if (resultsSection) {
    resultsSection.style.display = 'block';
    if (!prefersReducedMotion()) {
      setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth' }), 120);
    } else {
      resultsSection.scrollIntoView();
    }
  }

  const traceBox  = document.getElementById('traceSteps');
  const tracePill = document.getElementById('traceStatusPill');
  const wsBadgeText = document.getElementById('wsStatusText');
  const queryTitleEl = document.getElementById('resultsQueryTitle');

  if (queryTitleEl) queryTitleEl.textContent = `"${query}"`;
  if (traceBox)  traceBox.innerHTML = `<div class="trace-step-item" style="color:var(--gold);font-style:italic;">⏳ Initializing 5-node LangGraph pipeline…</div>`;
  if (tracePill) {
    tracePill.textContent = 'Executing…';
    tracePill.style.background = 'rgba(200,169,107,0.15)';
    tracePill.style.color = 'var(--gold)';
    tracePill.style.borderColor = 'rgba(200,169,107,0.35)';
  }

  // Show skeleton graph
  const skeleton = document.getElementById('skeletonGraph');
  const graphCanvas = document.getElementById('interactiveGraphCanvas');
  if (skeleton) skeleton.classList.add('visible');
  if (graphCanvas) graphCanvas.style.display = 'none';

  // Helper to clean up loading state in UI
  function cleanupLoadingUI(status = "done", errMsg = "") {
    if (searchBtnText) searchBtnText.textContent = 'Analyze';
    if (btnSpinner) btnSpinner.style.display = 'none';
    if (form) form.classList.remove('committed');
    
    if (status === "done") {
      if (tracePill) {
        tracePill.textContent = 'Done ✓';
        tracePill.style.background = 'rgba(110,139,106,0.15)';
        tracePill.style.color = 'var(--sage-mid)';
        tracePill.style.borderColor = 'rgba(110,139,106,0.35)';
      }
      setAllStagesDone();
    } else {
      if (tracePill) {
        tracePill.textContent = 'Error';
        tracePill.style.background = 'rgba(200,122,106,0.15)';
        tracePill.style.color = 'var(--red)';
      }
      if (traceBox && errMsg) {
        traceBox.innerHTML += `<div class="trace-step-item" style="color:var(--red);">❌ Error: ${errMsg}</div>`;
      }
      if (skeleton) skeleton.classList.remove('visible');
      if (graphCanvas) graphCanvas.style.display = 'block';
    }
  }

  // REST Fallback Action
  async function triggerRestFetch() {
    console.log("Triggering REST API fallback fetch");
    if (wsBadgeText) wsBadgeText.textContent = 'REST MODE';
    try {
      const apiHost = isPort8000 ? window.location.origin : 'http://localhost:8000';
      const resp = await fetch(`${apiHost}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: 10 }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);

      const data = await resp.json();
      globalContradictions = data.contradictions || [];
      globalGraphData = data.graph || { nodes: [], edges: [] };

      // Drive stage progress from actual backend steps
      if (data.steps && traceBox) {
        traceBox.innerHTML = '';
        data.steps.forEach((s, i) => {
          const idx = stepToStageIndex(s);
          if (idx) setStageActive(idx);
          const div = document.createElement('div');
          div.className = 'trace-step-item fade-in-up';
          div.style.animationDelay = prefersReducedMotion() ? '0ms' : `${i * 80}ms`;
          div.textContent = `⚡ ${s}`;
          traceBox.appendChild(div);
        });
      }

      cleanupLoadingUI("done");
      finishRender(globalGraphData, globalContradictions);
    } catch(err) {
      console.error('REST API fallback error:', err);
      cleanupLoadingUI("error", `${err.message}. Is the server running on port 8000?`);
    }
  }

  // WebSocket connection
  const isPort8000 = window.location.port === '8000';
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = isPort8000 ? window.location.host : 'localhost:8000';
  const wsUrl  = `${wsProtocol}//${wsHost}/ws/query`;

  let usedFallback = false;
  let wsTimeout = null;

  try {
    if (activeWebSocket) { try { activeWebSocket.close(); } catch(e){} }
    activeWebSocket = new WebSocket(wsUrl);

    // Timeout if WS doesn't open within 500ms
    wsTimeout = setTimeout(() => {
      if (activeWebSocket.readyState !== WebSocket.OPEN && !usedFallback) {
        console.warning("WebSocket connection timed out after 500ms. Falling back to REST.");
        usedFallback = true;
        try { activeWebSocket.close(); } catch(e){}
        triggerRestFetch();
      }
    }, 500);

    activeWebSocket.onopen = () => {
      if (wsTimeout) clearTimeout(wsTimeout);
      if (wsBadgeText) wsBadgeText.textContent = 'WS CONNECTED';
      activeWebSocket.send(JSON.stringify({ query }));
    };

    activeWebSocket.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'step') {
          const stageIdx = stepToStageIndex(msg.data);
          if (stageIdx) setStageActive(stageIdx);
          if (traceBox) {
            traceBox.innerHTML += `<div class="trace-step-item fade-in-up">⚡ ${msg.data}</div>`;
            traceBox.scrollTop = traceBox.scrollHeight;
          }
        } else if (msg.type === 'done') {
          if (msg.data) {
            if (msg.data.contradictions) globalContradictions = msg.data.contradictions;
            if (msg.data.graph) globalGraphData = msg.data.graph;
            cleanupLoadingUI("done");
            finishRender(globalGraphData, globalContradictions);
          }
        } else if (msg.type === 'error') {
          throw new Error(msg.data);
        }
      } catch(e) {
        console.error('WS msg parse/execution err', e);
        cleanupLoadingUI("error", e.message);
      }
    };

    activeWebSocket.onerror = (e) => {
      if (wsTimeout) clearTimeout(wsTimeout);
      console.warn("WebSocket error occurred:", e);
      if (!usedFallback) {
        usedFallback = true;
        triggerRestFetch();
      }
    };

    activeWebSocket.onclose = (e) => {
      if (wsTimeout) clearTimeout(wsTimeout);
      // Only fallback if connection closed before getting a result
      if (!usedFallback && e.code !== 1000) {
        usedFallback = true;
        triggerRestFetch();
      }
    };
  } catch(e) {
    if (wsTimeout) clearTimeout(wsTimeout);
    console.error('WebSocket initialization failed:', e);
    if (!usedFallback) {
      usedFallback = true;
      triggerRestFetch();
    }
  }
}

/* ── Finish render after data arrives ─ */
function finishRender(graphData, contradictions) {
  const skeleton = document.getElementById('skeletonGraph');
  const graphCanvas = document.getElementById('interactiveGraphCanvas');

  // Skeleton → real graph morph with a brief delay for visual effect
  const delay = prefersReducedMotion() ? 0 : 320;
  setTimeout(() => {
    if (skeleton) skeleton.classList.remove('visible');
    if (graphCanvas) { graphCanvas.style.display = 'block'; }
    renderInteractiveGraph(graphData, contradictions);
    renderLiveResults(contradictions);
  }, delay);
}

/* ── Graph controls ─ */
function zoomGraph(factor) {
  graphZoomScale *= factor;
  graphZoomScale = Math.max(0.5, Math.min(2.5, graphZoomScale));
  renderInteractiveGraph(globalGraphData, globalContradictions);
}
function resetGraphView() {
  graphZoomScale = 1.0; isClustered = false;
  const clusterBtn = document.getElementById('clusterToggleBtn');
  if (clusterBtn) clusterBtn.classList.remove('active');
  renderInteractiveGraph(globalGraphData, globalContradictions);
}
function toggleClusterNodes() {
  isClustered = !isClustered;
  const btn = document.getElementById('clusterToggleBtn');
  if (btn) btn.classList.toggle('active', isClustered);
  renderInteractiveGraph(globalGraphData, globalContradictions);
}

/* ── Render graph canvas ─ */
function renderInteractiveGraph(graphData, contradictions) {
  const canvas = document.getElementById('interactiveGraphCanvas');
  if (!canvas) return;
  const nodes = graphData.nodes || [];
  const edges = graphData.edges || [];

  if (nodes.length === 0 && (!contradictions || contradictions.length === 0)) {
    canvas.innerHTML = `<div style="display:flex;height:100%;align-items:center;justify-content:center;color:var(--text-muted);font-family:var(--font-mono);font-size:0.88rem;">No nodes. Submit a query above.</div>`;
    return;
  }

  const W = canvas.offsetWidth || 800;
  const H = canvas.offsetHeight || 480;
  const nodeCoords = {};
  const displayNodes = isClustered && nodes.length > 30 ? nodes.slice(0, 18) : nodes;

  let html = `<div style="transform:scale(${graphZoomScale});transform-origin:center center;transition:transform 0.3s ease;width:100%;height:100%;position:relative;">`;
  html += `<svg style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none;" id="graphSvgEdges"></svg>`;

  displayNodes.forEach((n, idx) => {
    const angle  = (idx / Math.max(displayNodes.length, 1)) * Math.PI * 2;
    const radius = n.type === 'entity' ? 110 : 200;
    const x = Math.round(W / 2 + Math.cos(angle) * radius);
    const y = Math.round(H / 2 + Math.sin(angle) * (radius * 0.65));
    nodeCoords[n.id] = { x, y };

    const typeClass = n.type === 'entity' ? 'rf-node-entity' : 'rf-node-source';
    const icon = n.type === 'entity' ? '◈' : '📄';
    const animDelay = prefersReducedMotion() ? '0ms' : `${idx * 60}ms`;

    html += `<div class="rf-node ${typeClass}" style="left:${x-65}px;top:${y-22}px;animation-delay:${animDelay};"
              onclick="handleNodeClick('${n.id}','${n.label}')" title="Click to trace sources">
              <span>${icon}</span><span>${n.label}</span></div>`;
  });

  if (isClustered && nodes.length > 30) {
    const cx = Math.round(W / 2 + 250), cy = Math.round(H / 2 + 150);
    html += `<div class="rf-node rf-node-entity" style="left:${cx-60}px;top:${cy-20}px;background:rgba(200,169,107,0.15);border-color:var(--gold);"
              onclick="toggleClusterNodes()" title="Expand">❖ +${nodes.length-18} more</div>`;
  }
  html += `</div>`;
  canvas.innerHTML = html;

  const svg = document.getElementById('graphSvgEdges');
  if (!svg) return;

  let svgContent = `<defs>
    <filter id="glowRed" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
    <filter id="glowSage" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>`;

  edges.forEach(e => {
    const src = nodeCoords[e.source], tgt = nodeCoords[e.target];
    if (!src || !tgt) return;
    const isContra = e.type === 'CONTRADICTS' || e.type.includes('CONTRADICTION') ||
                     e.type === 'METHODOLOGY_MISMATCH' || e.type === 'SCOPE_MISMATCH';
    const strokeColor = isContra ? 'var(--red)' : 'var(--sage-dark)';
    const dash  = isContra ? 'stroke-dasharray="6,6" style="animation:strokeDash 1s linear infinite;"' : '';
    const filter = isContra ? 'filter="url(#glowRed)"' : 'filter="url(#glowSage)"';
    svgContent += `<line x1="${src.x}" y1="${src.y}" x2="${tgt.x}" y2="${tgt.y}"
      stroke="${strokeColor}" stroke-width="${isContra?2.5:1.2}" opacity="${isContra?0.9:0.35}"
      ${dash} ${filter}/>`;
  });
  svg.innerHTML = svgContent;
}

/* ── Temporal slider ─ */
function setTemporalPreset(val) {
  const s = document.getElementById('temporalSlider');
  if (s) { s.value = val; handleTemporalSlide(val); }
}
function getGraphDataForContradictions(contradictions) {
  const nodes = [];
  const edges = [];
  const seenNodes = new Set();

  contradictions.forEach(c => {
    // Entity node
    const entId = `ent_${c.entity.toLowerCase().replace(/ /g, '_')}`;
    if (!seenNodes.has(entId)) {
      nodes.push({ id: entId, label: c.entity, type: 'entity' });
      seenNodes.add(entId);
    }

    // Source A node
    if (c.source_a) {
      const srcAId = `src_${c.source_a.source_name.toLowerCase().replace(/ /g, '_')}`;
      if (!seenNodes.has(srcAId)) {
        nodes.push({
          id: srcAId,
          label: c.source_a.source_name,
          type: 'source',
          data: { author: c.source_a.author, url: c.source_a.url }
        });
        seenNodes.add(srcAId);
      }
      // Support edge
      edges.push({
        id: `e_${srcAId}_${entId}`,
        source: srcAId,
        target: entId,
        type: 'SUPPORTS',
        data: { value: c.source_a.excerpt ? c.source_a.excerpt.slice(0, 40) : '' }
      });
    }

    // Source B node
    if (c.source_b) {
      const srcBId = `src_${c.source_b.source_name.toLowerCase().replace(/ /g, '_')}`;
      if (!seenNodes.has(srcBId)) {
        nodes.push({
          id: srcBId,
          label: c.source_b.source_name,
          type: 'source',
          data: { author: c.source_b.author, url: c.source_b.url }
        });
        seenNodes.add(srcBId);
      }
      // Support edge
      edges.push({
        id: `e_${srcBId}_${entId}`,
        source: srcBId,
        target: entId,
        type: 'SUPPORTS',
        data: { value: c.source_b.excerpt ? c.source_b.excerpt.slice(0, 40) : '' }
      });
    }

    // Contradiction edge
    if (c.source_a && c.source_b) {
      const srcAId = `src_${c.source_a.source_name.toLowerCase().replace(/ /g, '_')}`;
      const srcBId = `src_${c.source_b.source_name.toLowerCase().replace(/ /g, '_')}`;
      const edgeType = c.contradiction_type === 'direct_contradiction' ? 'CONTRADICTS' : c.contradiction_type.toUpperCase();
      edges.push({
        id: `e_contra_${c.id.slice(0, 8)}`,
        source: srcAId,
        target: srcBId,
        type: edgeType,
        data: { reason: c.reason, confidence: c.confidence, type: c.contradiction_type }
      });
    }
  });

  return { nodes, edges };
}

function handleTemporalSlide(val) {
  const badge = document.getElementById('temporalDateBadge');
  const num = parseInt(val, 10);
  
  let maxDate;
  if (num < 35) {
    maxDate = new Date("2024-05-15T23:59:59Z");
    if (badge) badge.textContent = 'May 15, 2024 — Early Reports';
  } else if (num < 70) {
    maxDate = new Date("2024-05-16T23:59:59Z");
    if (badge) badge.textContent = 'May 15–16, 2024 — Mid Period';
  } else {
    maxDate = new Date("2024-05-17T23:59:59Z");
    if (badge) badge.textContent = 'May 15–17, 2024 — Full Range';
  }

  const filtered = globalContradictions.filter(c => {
    const dateA = c.source_a && c.source_a.published_at ? new Date(c.source_a.published_at) : null;
    const dateB = c.source_b && c.source_b.published_at ? new Date(c.source_b.published_at) : null;
    
    const okA = !dateA || dateA <= maxDate;
    const okB = !dateB || dateB <= maxDate;
    return okA && okB;
  });

  const filteredGraph = getGraphDataForContradictions(filtered);
  renderLiveResults(filtered);
  renderInteractiveGraph(filteredGraph, filtered);
}

/* ── Source-tracing split view modal ─ */
function openSplitViewModal(cId) {
  const c = globalContradictions.find(x => x.id === cId) || globalContradictions[0];
  if (!c) return;

  const modal = document.getElementById('splitViewModal');
  document.getElementById('splitModalEntity').textContent = `${c.entity} — Contradiction Diagnosis`;

  const type = (c.contradiction_type || '').replace(/_/g, ' ').toUpperCase();
  const confPct = Math.round((c.confidence || 0.9) * 100);
  document.getElementById('splitModalType').textContent = `${type}`;

  // Confidence bar
  const confBar = document.getElementById('splitModalConfBar');
  const confPctEl = document.getElementById('splitModalConfPct');
  const confWrap = document.getElementById('splitModalConfidence');
  if (confBar && confPctEl && confWrap) {
    confBar.style.width = `${confPct}%`;
    confPctEl.textContent = `${confPct}%`;
    confWrap.className = 'confidence-wrap';
    if (confPct >= 85) confWrap.classList.add('confidence-high');
    else if (confPct >= 60) confWrap.classList.add('confidence-med');
    else confWrap.classList.add('confidence-low');
  }

  document.getElementById('splitModalReason').textContent = c.reason || 'No classifier explanation available.';

  // "Why not a contradiction" box for scope/methodology
  const whyBox  = document.getElementById('splitWhyNotBox');
  const whyText = document.getElementById('splitWhyNotText');
  const isFalsePositiveType = c.contradiction_type === 'scope_mismatch' ||
                               c.contradiction_type === 'methodology_mismatch' ||
                               c.contradiction_type === 'stale';
  if (whyBox && whyText) {
    if (isFalsePositiveType) {
      const explanations = {
        scope_mismatch: 'These sources are reporting on different time periods, geographies, or population scopes. They are answering different questions — this is not a genuine contradiction, and no correction is needed.',
        methodology_mismatch: 'These sources use different measurement approaches (e.g. CPI vs PCE, core vs headline, BLS survey vs spot market). The disagreement is about method, not about underlying facts.',
        stale: 'One of these sources is significantly older. The newer report likely supersedes the older one — this reflects an update to the data, not a conflict between simultaneous reports.',
      };
      whyText.textContent = explanations[c.contradiction_type] || 'This classification suggests the apparent conflict may not be a genuine disagreement on the same facts.';
      whyBox.style.display = 'block';
    } else {
      whyBox.style.display = 'none';
    }
  }

  const scopeA = (c.source_a && c.source_a.claimed_scope) || {};
  const scopeB = (c.source_b && c.source_b.claimed_scope) || {};

  const recencyA = recencyLabel(c.source_a && c.source_a.published_at);
  const recencyB = recencyLabel(c.source_b && c.source_b.published_at);

  const bodyEl = document.getElementById('splitModalBody');
  if (bodyEl) {
    bodyEl.innerHTML = `
      <div class="clause-card" style="border-top:3px solid var(--sage-mid);">
        <div class="clause-source-tag">
          Source A: ${c.source_a ? c.source_a.source_name : 'Primary Source'}
          ${recencyA}
        </div>
        <div style="font-size:0.8rem;color:var(--text-secondary);font-family:var(--font-mono);margin:0.35rem 0;">
          Author: ${(c.source_a && c.source_a.author) || 'Editorial Staff'} &nbsp;|&nbsp;
          Date: ${c.source_a && c.source_a.published_at ? strDate(c.source_a.published_at) : 'May 2024'}
        </div>
        <div class="scope-badge-group">
          <span class="scope-badge">📅 ${scopeA.date_range || 'May 2024'}</span>
          <span class="scope-badge">🌐 ${scopeA.geography || 'US'}</span>
          <span class="scope-badge">🔬 ${scopeA.methodology || 'Official Survey'}</span>
          <span class="scope-badge">📊 Sentiment: ${(c.source_a && c.source_a.sentiment != null) ? c.source_a.sentiment.toFixed(2) : 'N/A'}</span>
        </div>
        <div class="clause-excerpt">"${c.source_a ? c.source_a.excerpt : 'No excerpt.'}"</div>
        ${c.source_a && c.source_a.url ? `<a href="${c.source_a.url}" target="_blank" rel="noopener" style="display:inline-block;margin-top:0.75rem;font-size:0.78rem;color:var(--sage-mid);">↗ View Source Article</a>` : ''}
      </div>

      <div class="clause-card" style="border-top:3px solid var(--gold);">
        <div class="clause-source-tag" style="color:var(--gold);">
          Source B: ${c.source_b ? c.source_b.source_name : 'Secondary Source'}
          ${recencyB}
        </div>
        <div style="font-size:0.8rem;color:var(--text-secondary);font-family:var(--font-mono);margin:0.35rem 0;">
          Author: ${(c.source_b && c.source_b.author) || 'Editorial Staff'} &nbsp;|&nbsp;
          Date: ${c.source_b && c.source_b.published_at ? strDate(c.source_b.published_at) : 'May 2024'}
        </div>
        <div class="scope-badge-group">
          <span class="scope-badge">📅 ${scopeB.date_range || 'May 2024'}</span>
          <span class="scope-badge">🌐 ${scopeB.geography || 'US'}</span>
          <span class="scope-badge">🔬 ${scopeB.methodology || 'Proprietary Index'}</span>
          <span class="scope-badge">📊 Sentiment: ${(c.source_b && c.source_b.sentiment != null) ? c.source_b.sentiment.toFixed(2) : 'N/A'}</span>
        </div>
        <div class="clause-excerpt" style="border-left-color:var(--gold);">"${c.source_b ? c.source_b.excerpt : 'No excerpt.'}"</div>
        ${c.source_b && c.source_b.url ? `<a href="${c.source_b.url}" target="_blank" rel="noopener" style="display:inline-block;margin-top:0.75rem;font-size:0.78rem;color:var(--gold);">↗ View Source Article</a>` : ''}
      </div>
    `;
  }
  if (modal) modal.style.display = 'flex';
}

function closeSplitViewModal() {
  const modal = document.getElementById('splitViewModal');
  if (modal) modal.style.display = 'none';
}

/* ── Recency label helper ─ */
function recencyLabel(dtStr) {
  if (!dtStr) return '';
  const ms = Date.now() - new Date(dtStr).getTime();
  const days = ms / 86400000;
  if (days < 3)   return `<span class="source-recency-badge fresh">● Fresh</span>`;
  if (days < 30)  return `<span class="source-recency-badge">● Recent</span>`;
  return `<span class="source-recency-badge stale">● Older</span>`;
}

function strDate(dtStr) {
  try { return new Date(dtStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch(e) { return dtStr; }
}

/* ── Node click → open modal ─ */
function handleNodeClick(id, label) {
  if (globalContradictions && globalContradictions.length > 0) {
    let match = globalContradictions.find(c =>
      c.entity.toLowerCase().includes(label.toLowerCase())
    );
    if (!match) {
      match = globalContradictions.find(c =>
        (c.source_a && c.source_a.source_name.toLowerCase().includes(label.toLowerCase())) ||
        (c.source_b && c.source_b.source_name.toLowerCase().includes(label.toLowerCase()))
      );
    }
    if (!match) {
      match = globalContradictions[0];
    }
    openSplitViewModal(match.id);
  }
}

/* ── Render contradiction cards ─ */
function renderLiveResults(contradictions) {
  const list = document.getElementById('liveContradictionsList');
  if (!list) return;

  if (!contradictions || contradictions.length === 0) {
    list.innerHTML = `<div style="color:var(--text-muted);text-align:center;padding:3rem;font-family:var(--font-mono);font-size:0.88rem;">
      No contradictions detected in this query range.<br/>
      <span style="font-size:0.75rem;opacity:0.6;">The system will say so rather than guess — which is the right behavior.</span>
    </div>`;
    return;
  }

  list.innerHTML = contradictions.map((c, ci) => {
    const confPct = Math.round((c.confidence || 0.9) * 100);
    const confClass = confPct >= 85 ? 'confidence-high' : confPct >= 60 ? 'confidence-med' : 'confidence-low';
    const cType = (c.contradiction_type || 'unknown').replace(/_/g, ' ');
    const isFP = c.contradiction_type === 'scope_mismatch' ||
                 c.contradiction_type === 'methodology_mismatch' ||
                 c.contradiction_type === 'stale';

    const whyNotHtml = isFP ? `
      <div class="why-not-box">
        <div class="why-not-label">ℹ Why this is a "${cType}" — not a true contradiction</div>
        <div class="why-not-text">${
          c.contradiction_type === 'scope_mismatch'
            ? 'Sources cover different time periods or geographies — they are not answering the same question.'
            : c.contradiction_type === 'methodology_mismatch'
            ? 'Sources use different measurement methods (e.g. CPI vs PCE). The disagreement is about approach, not facts.'
            : 'One source is significantly older and likely superseded by the more recent report.'
        }</div>
      </div>` : '';

    const recencyA = recencyLabel(c.source_a && c.source_a.published_at);
    const recencyB = recencyLabel(c.source_b && c.source_b.published_at);
    const animDelay = prefersReducedMotion() ? '0ms' : `${ci * 90}ms`;

    return `
      <div class="live-contra-card fade-in-up" style="animation-delay:${animDelay};"
           onclick="openSplitViewModal('${c.id}')" title="Click to open source-tracing split view">
        <div class="contra-header-row">
          <span class="contra-entity-title">◈ ${c.entity}</span>
          <span class="contra-type-badge type-${c.contradiction_type}">
            ${cType}
          </span>
        </div>

        <!-- Confidence indicator -->
        <div class="confidence-wrap ${confClass}" style="margin-bottom:0.75rem;">
          <span class="confidence-label">Confidence</span>
          <div class="confidence-bar-track">
            <div class="confidence-bar-fill" style="width:${confPct}%;transition-delay:${animDelay};"></div>
          </div>
          <span class="confidence-pct">${confPct}%</span>
        </div>

        <p class="contra-reason-text">
          <strong>Classifier diagnosis:</strong> ${c.reason}
        </p>

        ${whyNotHtml}

        <div class="contra-sources-grid">
          <div class="source-box">
            <div class="source-box-title">
              Source A: ${c.source_a ? c.source_a.source_name : '—'} ${recencyA}
            </div>
            <p class="source-excerpt">"${c.source_a && c.source_a.excerpt ? c.source_a.excerpt.slice(0,150) : ''}…"</p>
          </div>
          <div class="source-box">
            <div class="source-box-title" style="color:var(--gold);">
              Source B: ${c.source_b ? c.source_b.source_name : '—'} ${recencyB}
            </div>
            <p class="source-excerpt">"${c.source_b && c.source_b.excerpt ? c.source_b.excerpt.slice(0,150) : ''}…"</p>
          </div>
        </div>

        <div style="margin-top:1rem;text-align:right;">
          <span style="font-family:var(--font-mono);font-size:0.75rem;color:var(--text-muted);">
            🔍 Click card to open source-tracing split view →
          </span>
        </div>
      </div>
    `;
  }).join('');
}

/* ── Showcase tab switching ─ */
function switchShowcaseTab(tabEl, target) {
  if (!tabEl) return;
  document.querySelectorAll('.showcase-tab-item').forEach(t => t.classList.remove('active'));
  tabEl.classList.add('active');
  if (target && target !== '#hero') {
    const el = document.querySelector(target);
    if (el) el.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }
}

/* ── Keyboard: Escape closes modal ─ */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeSplitViewModal();
});

function showLiveDemo(event) {
  if (event) event.preventDefault();
  const resultsSection = document.getElementById('live-results-section');
  if (resultsSection) {
    resultsSection.style.display = 'block';
  }
  const input = document.getElementById('queryInput');
  if (input) {
    input.focus();
    input.select();
  }
  if (resultsSection) {
    resultsSection.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }
}
