/* =====================================================
   OMNI-PERSPECTIVE ENGINE — main.js
   ===================================================== */

/* ── Reduced-motion utility ── */
const prefersReducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ── NAV scroll state ── */
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
  let W, H, nodes;

  const COLORS = {
    node_teal: 'rgba(214,159,151,0.80)',
    node_dim:  'rgba(214,159,151,0.15)',
    edge_teal: 'rgba(147,130,117,0.12)',
    edge_red:  'rgba(200,120,112,0.35)',
  };

  function resize() {
    W = canvas.width  = container.offsetWidth;
    H = canvas.height = container.offsetHeight;
    buildNodes();
  }
  function rand(a, b) { return a + Math.random() * (b - a); }
  function buildNodes() {
    nodes = Array.from({ length: 50 }, (_, i) => ({
      x: rand(0, W), y: rand(0, H),
      vx: rand(-0.18, 0.18), vy: rand(-0.15, 0.15),
      r: rand(2, 4.5),
      type: i < 4 ? 'accent' : (i < 16 ? 'teal' : 'dim'),
      pulse: rand(0, Math.PI * 2),
      pulseSpeed: rand(0.012, 0.025),
    }));
  }
  function drawFrame() {
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
        if (d > 150) continue;
        const isContra = a.type === 'accent' || b.type === 'accent';
        ctx.beginPath();
        ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = isContra ? COLORS.edge_red : COLORS.edge_teal;
        ctx.lineWidth = isContra ? 1.2 : 0.7;
        ctx.globalAlpha = 1 - d / 150;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }
    for (const n of nodes) {
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI*2);
      ctx.fillStyle = n.type === 'accent' ? 'rgba(200,120,112,0.75)'
                    : n.type === 'teal'   ? COLORS.node_teal
                    : COLORS.node_dim;
      ctx.fill();
    }
    if (!prefersReducedMotion()) requestAnimationFrame(drawFrame);
  }
  resize();
  window.addEventListener('resize', resize);
  requestAnimationFrame(drawFrame);
})();

/* =====================================================
   HERO LIVE DEMO CANVAS
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

  const TEAL  = '#D69F97';
  const RED   = '#C87870';
  const CREAM = '#2A221E';

  const entity  = { x: 300, y: 170, r: 38, label: 'INFLATION\nRATE 2024' };
  const sources = [
    { x: 100, y: 90,  label: 'Reuters',   val: '3.2%', color: TEAL },
    { x: 500, y: 80,  label: 'Bloomberg', val: '3.8%', color: RED  },
    { x: 90,  y: 270, label: 'FT',        val: '3.2%', color: TEAL },
    { x: 500, y: 270, label: 'AP',        val: '3.9%', color: RED  },
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
    ctx.clearRect(0, 0, W, H);

    // Support edges
    for (const s of sources) {
      ctx.setLineDash([]);
      ctx.strokeStyle = 'rgba(214,159,151,0.25)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(entity.x, entity.y); ctx.stroke();
    }

    // Contradiction edges
    ctx.save();
    for (const [ai, bi] of contradictPairs) {
      const a = sources[ai], b = sources[bi];
      const phase = t * 0.06;
      ctx.setLineDash([6, 4]);
      ctx.lineDashOffset = -phase;
      const pulse = 0.55 + 0.45 * Math.sin(t * 0.03 + ai);
      ctx.strokeStyle = `rgba(200,120,112,${0.5 + 0.4 * pulse})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();

      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      ctx.save();
      rr(mx-30, my-10, 60, 20, 3, `rgba(200,120,112,${0.12*pulse})`, `rgba(200,120,112,0.45)`);
      ctx.fillStyle = RED; ctx.font = '600 8px "JetBrains Mono",monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.setLineDash([]);
      ctx.fillText('CONFLICT', mx, my);
      ctx.restore();
    }
    ctx.restore();

    // Entity center node
    const ep = 0.5 + 0.5 * Math.sin(t * 0.018);
    ctx.beginPath(); ctx.arc(entity.x, entity.y, entity.r, 0, Math.PI*2);
    ctx.fillStyle = '#FAF7F3';
    ctx.strokeStyle = `rgba(214,159,151,${0.6 + 0.3*ep})`;
    ctx.lineWidth = 2; ctx.fill(); ctx.stroke();
    ctx.fillStyle = CREAM; ctx.font = 'bold 9px "Inter",sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    entity.label.split('\n').forEach((line, i) => ctx.fillText(line, entity.x, entity.y + (i - 0.5)*12));

    // Source nodes
    for (const s of sources) {
      rr(s.x-44, s.y-22, 88, 44, 6, '#F3E8D8', s.color);
      ctx.setLineDash([]);
      ctx.fillStyle = s.color; ctx.font = '600 10px "Inter",sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(s.label, s.x, s.y - 8);
      ctx.fillStyle = CREAM; ctx.font = '600 13px "JetBrains Mono",monospace';
      ctx.fillText(s.val, s.x, s.y + 8);
    }

    // Status line
    const alpha = 0.5 + 0.4 * Math.sin(t * 0.022);
    ctx.fillStyle = `rgba(200,120,112,${alpha})`;
    ctx.font = '600 9px "JetBrains Mono",monospace';
    ctx.textAlign = 'center';
    ctx.fillText('3 ACTIVE CONTRADICTIONS DETECTED', 300, 318);

    t++;
    requestAnimationFrame(drawLoop);
  }
  requestAnimationFrame(drawLoop);
})();

/* =====================================================
   LIVE QUERY ENGINE & GLOBAL STATE
   ===================================================== */
let globalContradictions = [];
let globalGraphData = { nodes: [], edges: [] };
let globalStepsTrace = [];
let globalQueryString = "";
let activeWebSocket = null;
let isClustered = false;
let graphZoomScale = 1.0;

/* Active Filter States */
let activeTaxonomyFilter = 'all';
let minConfidenceThreshold = 50; // percentage (50-95)
let currentTemporalVal = 100;

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

function stepToStageIndex(stepText) {
  if (/vector agent/i.test(stepText))   return 1;
  if (/crag agent/i.test(stepText))     return 2;
  if (/graph agent/i.test(stepText))    return 3;
  if (/synthesizer/i.test(stepText))    return 4;
  if (/classifier/i.test(stepText))     return 5;
  return null;
}

async function handleQuerySubmit(event) {
  if (event && event.preventDefault) event.preventDefault();
  const input = document.getElementById('queryInput');
  const query = input ? input.value.trim() : '';
  if (!query) return;

  globalQueryString = query;
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

  const resultsSection = document.getElementById('live-results-section');
  if (resultsSection) {
    resultsSection.style.display = 'block';
    setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth' }), 120);
  }

  const traceBox  = document.getElementById('traceSteps');
  const tracePill = document.getElementById('traceStatusPill');
  const wsBadgeText = document.getElementById('wsStatusText');
  const queryTitleEl = document.getElementById('resultsQueryTitle');

  if (queryTitleEl) queryTitleEl.textContent = `"${query}"`;
  if (traceBox)  traceBox.innerHTML = `<div class="trace-step-item" style="color:var(--gold);font-style:italic;">⏳ Initializing 5-node LangGraph pipeline...</div>`;
  if (tracePill) {
    tracePill.textContent = 'Executing…';
    tracePill.style.background = 'rgba(200,169,107,0.15)';
    tracePill.style.color = 'var(--gold)';
  }

  const skeleton = document.getElementById('skeletonGraph');
  const graphCanvas = document.getElementById('interactiveGraphCanvas');
  if (skeleton) skeleton.classList.add('visible');
  if (graphCanvas) graphCanvas.style.display = 'none';

  function cleanupLoadingUI(status = 'done', errMsg = '') {
    if (searchBtnText) searchBtnText.textContent = 'Analyze';
    if (btnSpinner) btnSpinner.style.display = 'none';
    if (form) form.classList.remove('committed');
    if (status === 'done') {
      if (tracePill) {
        tracePill.textContent = 'Done ✓';
        tracePill.style.background = 'rgba(20,184,166,0.12)';
        tracePill.style.color = 'var(--sage-mid)';
      }
      setAllStagesDone();
    } else {
      if (tracePill) {
        tracePill.textContent = 'Error';
        tracePill.style.background = 'rgba(248,113,113,0.12)';
        tracePill.style.color = 'var(--red)';
      }
      if (traceBox && errMsg) {
        traceBox.innerHTML += `<div class="trace-step-item" style="color:var(--red);">❌ ${errMsg}</div>`;
      }
      if (skeleton) skeleton.classList.remove('visible');
      if (graphCanvas) graphCanvas.style.display = 'block';
    }
  }

  async function triggerRestFetch() {
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
      globalStepsTrace = data.steps || [];

      if (data.steps && traceBox) {
        traceBox.innerHTML = '';
        data.steps.forEach((s, i) => {
          const idx = stepToStageIndex(s);
          if (idx) setStageActive(idx);
          const div = document.createElement('div');
          div.className = 'trace-step-item fade-in-up';
          div.style.animationDelay = `${i * 80}ms`;
          div.textContent = `⚡ ${s}`;
          traceBox.appendChild(div);
        });
      }
      cleanupLoadingUI('done');
      finishRender();
    } catch(err) {
      cleanupLoadingUI('error', `${err.message}. Is the server running on port 8000?`);
    }
  }

  const isPort8000 = window.location.port === '8000';
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = isPort8000 ? window.location.host : 'localhost:8000';
  const wsUrl  = `${wsProtocol}//${wsHost}/ws/query`;

  let usedFallback = false;
  let wsTimeout = null;

  try {
    if (activeWebSocket) { try { activeWebSocket.close(); } catch(e){} }
    activeWebSocket = new WebSocket(wsUrl);

    wsTimeout = setTimeout(() => {
      if (activeWebSocket.readyState !== WebSocket.OPEN && !usedFallback) {
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
          globalStepsTrace.push(msg.data);
        } else if (msg.type === 'done') {
          if (msg.data) {
            if (msg.data.contradictions) globalContradictions = msg.data.contradictions;
            if (msg.data.graph) globalGraphData = msg.data.graph;
            if (msg.data.steps) globalStepsTrace = msg.data.steps;
            cleanupLoadingUI('done');
            finishRender();
          }
        } else if (msg.type === 'error') {
          throw new Error(msg.data);
        }
      } catch(e) {
        cleanupLoadingUI('error', e.message);
      }
    };

    activeWebSocket.onerror = () => {
      if (wsTimeout) clearTimeout(wsTimeout);
      if (!usedFallback) { usedFallback = true; triggerRestFetch(); }
    };

    activeWebSocket.onclose = (e) => {
      if (wsTimeout) clearTimeout(wsTimeout);
      if (!usedFallback && e.code !== 1000) { usedFallback = true; triggerRestFetch(); }
    };
  } catch(e) {
    if (wsTimeout) clearTimeout(wsTimeout);
    if (!usedFallback) { usedFallback = true; triggerRestFetch(); }
  }
}

/* ── Render after data arrives ── */
function finishRender() {
  const skeleton = document.getElementById('skeletonGraph');
  const graphCanvas = document.getElementById('interactiveGraphCanvas');
  const delay = prefersReducedMotion() ? 0 : 280;
  setTimeout(() => {
    if (skeleton) skeleton.classList.remove('visible');
    if (graphCanvas) graphCanvas.style.display = 'block';
    applyGlobalFilters();
  }, delay);
}

/* =====================================================
   MULTI-DIMENSIONAL FILTER CONTROL SYSTEM
   ===================================================== */
function filterByTaxonomy(taxType, btnEl) {
  activeTaxonomyFilter = taxType;
  if (btnEl) {
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    btnEl.classList.add('active');
  }
  applyGlobalFilters();
}

function handleConfSliderChange(val) {
  minConfidenceThreshold = parseInt(val, 10);
  const badge = document.getElementById('minConfBadge');
  if (badge) badge.textContent = `${minConfidenceThreshold}%+`;
  applyGlobalFilters();
}

function applyGlobalFilters() {
  let filtered = globalContradictions.filter(c => {
    // 1. Taxonomy Filter
    if (activeTaxonomyFilter !== 'all' && c.contradiction_type !== activeTaxonomyFilter) {
      return false;
    }
    // 2. Confidence Filter
    const confPct = Math.round((c.confidence || 0.9) * 100);
    if (confPct < minConfidenceThreshold) {
      return false;
    }
    // 3. Timeline Filter
    const maxDate = currentTemporalVal < 35
      ? new Date('2024-05-15T23:59:59Z')
      : currentTemporalVal < 70
      ? new Date('2024-05-16T23:59:59Z')
      : new Date('2024-05-17T23:59:59Z');
    
    const dA = c.source_a?.published_at ? new Date(c.source_a.published_at) : null;
    const dB = c.source_b?.published_at ? new Date(c.source_b.published_at) : null;
    if (dA && dA > maxDate) return false;
    if (dB && dB > maxDate) return false;

    return true;
  });

  renderLiveResults(filtered);
  const filteredGraph = getGraphDataForContradictions(filtered);
  renderInteractiveGraph(filteredGraph, filtered);
}

/* ── Graph controls ── */
function zoomGraph(factor) {
  graphZoomScale = Math.max(0.5, Math.min(2.5, graphZoomScale * factor));
  renderInteractiveGraph(globalGraphData, globalContradictions);
}
function resetGraphView() {
  graphZoomScale = 1.0; isClustered = false;
  const btn = document.getElementById('clusterToggleBtn');
  if (btn) btn.classList.remove('active');
  renderInteractiveGraph(globalGraphData, globalContradictions);
}
function toggleClusterNodes() {
  isClustered = !isClustered;
  const btn = document.getElementById('clusterToggleBtn');
  if (btn) btn.classList.toggle('active', isClustered);
  renderInteractiveGraph(globalGraphData, globalContradictions);
}

/* ── Render graph canvas ── */
function renderInteractiveGraph(graphData, contradictions) {
  const canvas = document.getElementById('interactiveGraphCanvas');
  if (!canvas) return;
  const nodes = graphData.nodes || [];
  const edges = graphData.edges || [];

  if (nodes.length === 0 && (!contradictions || contradictions.length === 0)) {
    canvas.innerHTML = `<div style="display:flex;height:100%;align-items:center;justify-content:center;color:var(--text-muted);font-family:var(--font-mono);font-size:0.88rem;">No matching nodes for current filters. Submit a query above or lower confidence slider.</div>`;
    return;
  }

  const W = canvas.offsetWidth || 800;
  const H = canvas.offsetHeight || 480;
  const nodeCoords = {};
  const displayNodes = isClustered && nodes.length > 30 ? nodes.slice(0, 18) : nodes;

  let html = `<div style="transform:scale(${graphZoomScale});transform-origin:center center;transition:transform 200ms ease-out;width:100%;height:100%;position:relative;">`;
  html += `<svg style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none;" id="graphSvgEdges"></svg>`;

  displayNodes.forEach((n, idx) => {
    const angle  = (idx / Math.max(displayNodes.length, 1)) * Math.PI * 2;
    const radius = n.type === 'entity' ? 110 : 200;
    const x = Math.round(W / 2 + Math.cos(angle) * radius);
    const y = Math.round(H / 2 + Math.sin(angle) * (radius * 0.65));
    nodeCoords[n.id] = { x, y };

    const typeClass = n.type === 'entity' ? 'rf-node-entity' : 'rf-node-source';
    const animDelay = prefersReducedMotion() ? '0ms' : `${idx * 55}ms`;
    html += `<div class="rf-node ${typeClass}" style="left:${x-65}px;top:${y-22}px;animation-delay:${animDelay};"
              onclick="handleNodeClick('${n.id}','${n.label}')" title="Click to trace sources">
              <span>${n.type === 'entity' ? '◈' : '◉'}</span><span>${n.label}</span></div>`;
  });

  if (isClustered && nodes.length > 30) {
    const cx = Math.round(W / 2 + 250), cy = Math.round(H / 2 + 150);
    html += `<div class="rf-node rf-node-entity" style="left:${cx-60}px;top:${cy-20}px;opacity:0.6;"
              onclick="toggleClusterNodes()">+${nodes.length-18} more</div>`;
  }
  html += `</div>`;
  canvas.innerHTML = html;

  const svg = document.getElementById('graphSvgEdges');
  if (!svg) return;

  let svgContent = '';
  edges.forEach(e => {
    const src = nodeCoords[e.source], tgt = nodeCoords[e.target];
    if (!src || !tgt) return;
    const isContra = e.type === 'CONTRADICTS' || (e.type || '').includes('CONTRADICTION') ||
                     e.type === 'METHODOLOGY_MISMATCH' || e.type === 'SCOPE_MISMATCH';
    const dash = isContra ? 'stroke-dasharray="6,4"' : '';
    svgContent += `<line x1="${src.x}" y1="${src.y}" x2="${tgt.x}" y2="${tgt.y}"
      stroke="${isContra ? '#F87171' : 'rgba(71,85,105,0.45)'}"
      stroke-width="${isContra ? 2 : 1}" opacity="${isContra ? 0.85 : 0.4}"
      ${dash}/>`;
  });
  svg.innerHTML = svgContent;
}

/* ── Temporal slider ── */
function setTemporalPreset(val) {
  const s = document.getElementById('temporalSlider');
  if (s) { s.value = val; handleTemporalSlide(val); }
}

function getGraphDataForContradictions(contradictions) {
  const nodes = [], edges = [];
  const seenNodes = new Set();
  contradictions.forEach(c => {
    const entId = `ent_${c.entity.toLowerCase().replace(/ /g, '_')}`;
    if (!seenNodes.has(entId)) { nodes.push({ id: entId, label: c.entity, type: 'entity' }); seenNodes.add(entId); }
    ['source_a', 'source_b'].forEach(key => {
      if (!c[key]) return;
      const sId = `src_${c[key].source_name.toLowerCase().replace(/ /g, '_')}`;
      if (!seenNodes.has(sId)) { nodes.push({ id: sId, label: c[key].source_name, type: 'source' }); seenNodes.add(sId); }
      edges.push({ id: `e_${sId}_${entId}`, source: sId, target: entId, type: 'SUPPORTS' });
    });
    if (c.source_a && c.source_b) {
      const aId = `src_${c.source_a.source_name.toLowerCase().replace(/ /g, '_')}`;
      const bId = `src_${c.source_b.source_name.toLowerCase().replace(/ /g, '_')}`;
      edges.push({ id: `e_contra_${c.id.slice(0,8)}`, source: aId, target: bId, type: c.contradiction_type === 'direct_contradiction' ? 'CONTRADICTS' : c.contradiction_type.toUpperCase() });
    }
  });
  return { nodes, edges };
}

function handleTemporalSlide(val) {
  currentTemporalVal = parseInt(val, 10);
  const badge = document.getElementById('temporalDateBadge');
  if (currentTemporalVal < 35) {
    if (badge) badge.textContent = 'May 15, 2024';
  } else if (currentTemporalVal < 70) {
    if (badge) badge.textContent = 'May 15–16, 2024';
  } else {
    if (badge) badge.textContent = 'Full Range';
  }
  applyGlobalFilters();
}

/* ── Split view modal ── */
function openSplitViewModal(cId) {
  const c = globalContradictions.find(x => x.id === cId) || globalContradictions[0];
  if (!c) return;

  document.getElementById('splitModalEntity').textContent = `${c.entity} — Contradiction Diagnosis`;
  const type = (c.contradiction_type || '').replace(/_/g, ' ').toUpperCase();
  const confPct = Math.round((c.confidence || 0.9) * 100);
  document.getElementById('splitModalType').textContent = type;

  const confBar   = document.getElementById('splitModalConfBar');
  const confPctEl = document.getElementById('splitModalConfPct');
  const confWrap  = document.getElementById('splitModalConfidence');
  if (confBar && confPctEl && confWrap) {
    confBar.style.width = `${confPct}%`;
    confPctEl.textContent = `${confPct}%`;
    confWrap.className = 'confidence-wrap';
    confWrap.classList.add(confPct >= 85 ? 'confidence-high' : confPct >= 60 ? 'confidence-med' : 'confidence-low');
  }

  document.getElementById('splitModalReason').textContent = c.reason || 'No classifier explanation available.';

  // Render AI Resolution Recommendation
  const resBox  = document.getElementById('splitResolutionBox');
  const resText = document.getElementById('splitResolutionText');
  if (resBox && resText) {
    resText.textContent = c.ai_resolution || 'Reconciliation: Cross-reference primary survey scope against spot market index methodologies.';
  }

  const whyBox  = document.getElementById('splitWhyNotBox');
  const whyText = document.getElementById('splitWhyNotText');
  const isFP = ['scope_mismatch', 'methodology_mismatch', 'stale'].includes(c.contradiction_type);
  if (whyBox && whyText) {
    if (isFP) {
      const explanations = {
        scope_mismatch: 'These sources cover different time periods or geographies — they are answering different questions.',
        methodology_mismatch: 'These sources use different measurement methods (e.g. CPI vs PCE). The disagreement is about approach, not facts.',
        stale: 'One source is significantly older and likely superseded by the more recent report.',
      };
      whyText.textContent = explanations[c.contradiction_type] || '';
      whyBox.style.display = 'block';
    } else {
      whyBox.style.display = 'none';
    }
  }

  const scopeA = c.source_a?.claimed_scope || {};
  const scopeB = c.source_b?.claimed_scope || {};

  document.getElementById('splitModalBody').innerHTML = `
    <div class="clause-card" style="border-top:3px solid var(--sage-mid);">
      <div class="clause-source-tag">Source A: ${c.source_a?.source_name || '—'} ${recencyLabel(c.source_a?.published_at)}</div>
      <div style="font-size:0.8rem;color:var(--text-secondary);font-family:var(--font-mono);margin:0.35rem 0;">
        Author: ${c.source_a?.author || 'Editorial'} &nbsp;|&nbsp; Date: ${strDate(c.source_a?.published_at)}
      </div>
      <div class="scope-badge-group">
        <span class="scope-badge">📅 ${scopeA.date_range || 'May 2024'}</span>
        <span class="scope-badge">🌐 ${scopeA.geography || 'US'}</span>
        <span class="scope-badge">🔬 ${scopeA.methodology || 'Official Survey'}</span>
      </div>
      <div class="clause-excerpt">"${c.source_a?.excerpt || 'No excerpt.'}"</div>
      ${c.source_a?.url ? `<a href="${c.source_a.url}" target="_blank" rel="noopener" class="source-link">↗ View Source</a>` : ''}
    </div>
    <div class="clause-card" style="border-top:3px solid var(--gold);">
      <div class="clause-source-tag" style="color:var(--gold);">Source B: ${c.source_b?.source_name || '—'} ${recencyLabel(c.source_b?.published_at)}</div>
      <div style="font-size:0.8rem;color:var(--text-secondary);font-family:var(--font-mono);margin:0.35rem 0;">
        Author: ${c.source_b?.author || 'Editorial'} &nbsp;|&nbsp; Date: ${strDate(c.source_b?.published_at)}
      </div>
      <div class="scope-badge-group">
        <span class="scope-badge">📅 ${scopeB.date_range || 'May 2024'}</span>
        <span class="scope-badge">🌐 ${scopeB.geography || 'US'}</span>
        <span class="scope-badge">🔬 ${scopeB.methodology || 'Proprietary Index'}</span>
      </div>
      <div class="clause-excerpt" style="border-left-color:var(--gold);">"${c.source_b?.excerpt || 'No excerpt.'}"</div>
      ${c.source_b?.url ? `<a href="${c.source_b.url}" target="_blank" rel="noopener" class="source-link" style="color:var(--gold);">↗ View Source</a>` : ''}
    </div>
  `;

  document.getElementById('splitViewModal').style.display = 'flex';
}

function closeSplitViewModal() {
  document.getElementById('splitViewModal').style.display = 'none';
}

function recencyLabel(dtStr) {
  if (!dtStr) return '';
  const days = (Date.now() - new Date(dtStr).getTime()) / 86400000;
  if (days < 3)  return `<span class="source-recency-badge fresh">● Fresh</span>`;
  if (days < 30) return `<span class="source-recency-badge">● Recent</span>`;
  return `<span class="source-recency-badge stale">● Older</span>`;
}

function strDate(dtStr) {
  if (!dtStr) return 'May 2024';
  try { return new Date(dtStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch(e) { return dtStr; }
}

function handleNodeClick(id, label) {
  if (!globalContradictions.length) return;
  const match = globalContradictions.find(c => c.entity.toLowerCase().includes(label.toLowerCase()))
             || globalContradictions.find(c =>
                  c.source_a?.source_name.toLowerCase().includes(label.toLowerCase()) ||
                  c.source_b?.source_name.toLowerCase().includes(label.toLowerCase()))
             || globalContradictions[0];
  if (match) openSplitViewModal(match.id);
}

/* ── Render contradiction cards ── */
function renderLiveResults(contradictions) {
  const list = document.getElementById('liveContradictionsList');
  if (!list) return;

  if (!contradictions || contradictions.length === 0) {
    list.innerHTML = `<div style="color:var(--text-muted);text-align:center;padding:3rem;font-family:var(--font-mono);font-size:0.88rem;">
      No contradictions match the current taxonomy and confidence filters.<br/>
      <span style="font-size:0.75rem;opacity:0.6;">Try lowering the confidence slider or switching to 'All Types'.</span>
    </div>`;
    return;
  }

  list.innerHTML = contradictions.map((c, ci) => {
    const confPct  = Math.round((c.confidence || 0.9) * 100);
    const confClass = confPct >= 85 ? 'confidence-high' : confPct >= 60 ? 'confidence-med' : 'confidence-low';
    const cType = (c.contradiction_type || 'unknown').replace(/_/g, ' ');
    const isFP = ['scope_mismatch', 'methodology_mismatch', 'stale'].includes(c.contradiction_type);

    const resolutionHtml = c.ai_resolution ? `
      <div class="resolution-box" style="margin-bottom:0.75rem;">
        <div class="resolution-label">🤖 AI Resolution:</div>
        <div class="resolution-text">${c.ai_resolution}</div>
      </div>
    ` : '';

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

    return `
      <div class="live-contra-card fade-in-up" style="animation-delay:${ci * 80}ms;"
           onclick="openSplitViewModal('${c.id}')">
        <div class="contra-header-row">
          <span class="contra-entity-title">◈ ${c.entity}</span>
          <span class="contra-type-badge type-${c.contradiction_type}">${cType}</span>
        </div>
        <div class="confidence-wrap ${confClass}" style="margin-bottom:0.75rem;">
          <span class="confidence-label">Confidence</span>
          <div class="confidence-bar-track">
            <div class="confidence-bar-fill" style="width:${confPct}%;"></div>
          </div>
          <span class="confidence-pct">${confPct}%</span>
        </div>
        <p class="contra-reason-text"><strong>Classifier:</strong> ${c.reason}</p>
        ${resolutionHtml}
        ${whyNotHtml}
        <div class="contra-sources-grid">
          <div class="source-box">
            <div class="source-box-title">Source A: ${c.source_a?.source_name || '—'} ${recencyLabel(c.source_a?.published_at)}</div>
            <p class="source-excerpt">"${(c.source_a?.excerpt || '').slice(0,150)}…"</p>
          </div>
          <div class="source-box">
            <div class="source-box-title" style="color:var(--gold);">Source B: ${c.source_b?.source_name || '—'} ${recencyLabel(c.source_b?.published_at)}</div>
            <p class="source-excerpt">"${(c.source_b?.excerpt || '').slice(0,150)}…"</p>
          </div>
        </div>
        <div style="margin-top:1rem;text-align:right;">
          <span style="font-family:var(--font-mono);font-size:0.72rem;color:var(--text-muted);">Click to open source-tracing view →</span>
        </div>
      </div>
    `;
  }).join('');
}

/* =====================================================
   CUSTOM INGESTION MODAL HANDLERS
   ===================================================== */
function openIngestModal() {
  const modal = document.getElementById('ingestModal');
  if (modal) modal.style.display = 'flex';
}
function closeIngestModal() {
  const modal = document.getElementById('ingestModal');
  if (modal) modal.style.display = 'none';
}

async function handleCustomIngestSubmit(event) {
  if (event && event.preventDefault) event.preventDefault();

  const source_name = document.getElementById('ingestSourceName').value.trim();
  const title       = document.getElementById('ingestTitle').value.trim();
  const content     = document.getElementById('ingestContent').value.trim();
  const author      = document.getElementById('ingestAuthor').value.trim() || undefined;
  const url         = document.getElementById('ingestUrl').value.trim() || undefined;

  const btn = document.getElementById('ingestSubmitBtn');
  const feedback = document.getElementById('ingestFeedback');

  if (btn) btn.textContent = '⏳ Indexing…';
  if (feedback) {
    feedback.style.display = 'block';
    feedback.style.background = 'rgba(200,169,107,0.15)';
    feedback.style.color = 'var(--gold)';
    feedback.textContent = 'Indexing article content into Qdrant & database...';
  }

  try {
    const isPort8000 = window.location.port === '8000';
    const apiHost = isPort8000 ? window.location.origin : 'http://localhost:8000';
    const resp = await fetch(`${apiHost}/ingest/custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_name, title, content, author, url }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    const data = await resp.json();

    if (feedback) {
      feedback.style.background = 'rgba(20,184,166,0.15)';
      feedback.style.color = 'var(--teal)';
      feedback.textContent = `✓ ${data.message}`;
    }
    setTimeout(() => {
      closeIngestModal();
      document.getElementById('customIngestForm').reset();
      if (feedback) feedback.style.display = 'none';
      if (btn) btn.textContent = '⚡ Index Article';
    }, 1200);

  } catch(err) {
    if (feedback) {
      feedback.style.background = 'rgba(248,113,113,0.15)';
      feedback.style.color = 'var(--red)';
      feedback.textContent = `❌ Indexing error: ${err.message}`;
    }
    if (btn) btn.textContent = '⚡ Index Article';
  }
}

/* =====================================================
   INGESTION STATUS MODAL HANDLERS
   ===================================================== */
async function openStatusModal() {
  const modal = document.getElementById('statusModal');
  if (modal) modal.style.display = 'flex';

  const bodyEl = document.getElementById('statusModalBody');
  if (!bodyEl) return;
  bodyEl.innerHTML = `⏳ Fetching database & vector index statistics…`;

  try {
    const isPort8000 = window.location.port === '8000';
    const apiHost = isPort8000 ? window.location.origin : 'http://localhost:8000';
    const resp = await fetch(`${apiHost}/ingest/status`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (!data.sources || data.sources.length === 0) {
      bodyEl.innerHTML = `<div style="color:var(--text-muted);">No ingestion runs logged yet. Click below to trigger a background poll.</div>`;
      return;
    }

    bodyEl.innerHTML = `
      <table style="width:100%; border-collapse:collapse; text-align:left;">
        <thead>
          <tr style="border-bottom:1px solid var(--border); color:var(--teal);">
            <th style="padding:0.4rem;">Source</th>
            <th style="padding:0.4rem;">Status</th>
            <th style="padding:0.4rem;">Fetched</th>
            <th style="padding:0.4rem;">Chunks</th>
            <th style="padding:0.4rem;">Last Poll</th>
          </tr>
        </thead>
        <tbody>
          ${data.sources.map(s => `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:0.4rem; font-weight:600;">${s.source}</td>
              <td style="padding:0.4rem;"><span style="color:${s.status==='done'?'var(--teal)':'var(--gold)'}">${s.status}</span></td>
              <td style="padding:0.4rem;">${s.articles_fetched}</td>
              <td style="padding:0.4rem;">${s.chunks_created}</td>
              <td style="padding:0.4rem; opacity:0.7;">${s.last_run ? strDate(s.last_run) : 'Never'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch(err) {
    bodyEl.innerHTML = `<div style="color:var(--red);">Error loading status: ${err.message}. Is backend running on port 8000?</div>`;
  }
}

function closeStatusModal() {
  const modal = document.getElementById('statusModal');
  if (modal) modal.style.display = 'none';
}

async function triggerManualPoll(btnEl) {
  if (btnEl) btnEl.textContent = '⏳ Triggering…';
  try {
    const isPort8000 = window.location.port === '8000';
    const apiHost = isPort8000 ? window.location.origin : 'http://localhost:8000';
    await fetch(`${apiHost}/ingest/trigger`, { method: 'POST' });
    if (btnEl) btnEl.textContent = '✓ Poll Triggered!';
    setTimeout(() => { openStatusModal(); if (btnEl) btnEl.textContent = '🔄 Trigger Ingestion Poll'; }, 1500);
  } catch(err) {
    if (btnEl) btnEl.textContent = '❌ Failed';
  }
}

/* =====================================================
   REPORT EXPORT GENERATOR
   ===================================================== */
function exportAnalysisReport(format) {
  if (!globalContradictions || globalContradictions.length === 0) {
    alert("No active contradictions to export. Submit a query first.");
    return;
  }

  const queryName = globalQueryString || "contradiction-analysis";

  if (format === 'json') {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
      query: globalQueryString,
      timestamp: new Date().toISOString(),
      contradictions_count: globalContradictions.length,
      contradictions: globalContradictions,
      agent_trace: globalStepsTrace,
    }, null, 2));

    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${queryName.toLowerCase().replace(/[^a-z0-9]/g, '_')}_report.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();

  } else {
    // Markdown export
    let md = `# Omni-Perspective Engine — Contradiction Analysis Report\n\n`;
    md += `**Query**: \`${globalQueryString}\`  \n`;
    md += `**Generated**: ${new Date().toUTCString()}  \n`;
    md += `**Detected Contradictions**: ${globalContradictions.length}  \n\n`;
    md += `---  \n\n`;

    globalContradictions.forEach((c, idx) => {
      md += `## ${idx + 1}. Entity: ${c.entity}\n`;
      md += `- **Taxonomy Type**: \`${c.contradiction_type}\`  \n`;
      md += `- **Classifier Confidence**: \`${Math.round(c.confidence * 100)}%\`  \n`;
      md += `- **Diagnosis**: ${c.reason}  \n`;
      if (c.ai_resolution) {
        md += `- **AI Resolution**: ${c.ai_resolution}  \n`;
      }
      md += `\n### Source Attribution:\n`;
      md += `- **Source A (${c.source_a.source_name})**: "${c.source_a.excerpt}"  \n`;
      md += `- **Source B (${c.source_b.source_name})**: "${c.source_b.excerpt}"  \n\n`;
      md += `---  \n\n`;
    });

    md += `## Agent Pipeline Execution Trace\n`;
    globalStepsTrace.forEach(step => {
      md += `- ${step}\n`;
    });

    const dataStr = "data:text/markdown;charset=utf-8," + encodeURIComponent(md);
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${queryName.toLowerCase().replace(/[^a-z0-9]/g, '_')}_report.md`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }
}

/* ── Keyboard: Escape closes modal ── */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeSplitViewModal();
    closeIngestModal();
    closeStatusModal();
  }
});

function showLiveDemo(event) {
  if (event) event.preventDefault();
  const resultsSection = document.getElementById('live-results-section');
  if (resultsSection) resultsSection.style.display = 'block';
  const input = document.getElementById('queryInput');
  if (input) { input.focus(); input.select(); }
  if (resultsSection) resultsSection.scrollIntoView({ behavior: 'smooth' });
}
