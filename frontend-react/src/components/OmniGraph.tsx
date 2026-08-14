import React, { useMemo, useEffect, useCallback, useState } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  Node,
  Edge,
  Position,
} from '@xyflow/react';
import dagre from 'dagre';

import '@xyflow/react/dist/style.css';

import { useGraphStore, Contradiction } from '../store/useGraphStore';
import { useGraphStream } from '../hooks/useGraphStream';
import { parseCommandQuery } from '../services/api';
import { ContradictionCategory } from '../types/graph';

import { EntityNode } from './nodes/EntityNode';
import { ClaimNode } from './nodes/ClaimNode';
import { ContradictionEdge } from './edges/ContradictionEdge';

// Rule #1: ConsensusEdge removed — consensus edges now render as the default
// ReactFlow bezier edge (neutral, low-attention). Only conflict gets the accent.
const nodeTypes = {
  entityNode: EntityNode,
  claimNode: ClaimNode,
};

const edgeTypes = {
  contradictionEdge: ContradictionEdge,
  // consensusEdge handled by ReactFlow default (thin, neutral)
};

const nodeWidth = 190;
const nodeHeight = 85;

/**
 * Dagre layout — horizontal LR flow.
 */
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 48, ranksep: 88 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });
  dagre.layout(dagreGraph);

  const layoutedNodes: Node[] = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: Position.Left,
      sourcePosition: Position.Right,
      position: {
        x: nodeWithPosition ? nodeWithPosition.x - nodeWidth / 2 : 0,
        y: nodeWithPosition ? nodeWithPosition.y - nodeHeight / 2 : 0,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

// ─── Palette (Rule #1) ────────────────────────────────────────────────────────
// bg:       #070C14  (canvas)
// surface:  #0D1520  (nodes / panels)
// surface2: #111920  (hover shift)
// muted:    #475569  (secondary text)
// text:     #E2E8F0  (primary text)
// accent:   #14B8A6  (entity node accent ONLY — teal)
// danger:   #F87171  (contradiction ONLY — coral)
// ─────────────────────────────────────────────────────────────────────────────

const GraphCanvas: React.FC = () => {
  const { fitView } = useReactFlow();

  const storeNodes = useGraphStore(state => state.nodes);
  const storeEdges = useGraphStore(state => state.edges);
  const selectedElement = useGraphStore(state => state.selectedElement);
  const selectNode = useGraphStore(state => state.selectNode);
  const selectEdge = useGraphStore(state => state.selectEdge);
  const closePanel = useGraphStore(state => state.closePanel);
  const collapsedEntities = useGraphStore(state => state.collapsedEntities);
  const toggleEntityCollapse = useGraphStore(state => state.toggleEntityCollapse);
  const allContradictions = useGraphStore(state => state.allContradictions);

  const searchQuery = useGraphStore(state => state.searchQuery);
  const setSearchQuery = useGraphStore(state => state.setSearchQuery);
  const showOnlyContradictions = useGraphStore(state => state.showOnlyContradictions);
  const setShowOnlyContradictions = useGraphStore(state => state.setShowOnlyContradictions);

  const { stage, progressPct, message, isStreaming, error, executeStreamQuery } = useGraphStream();

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [isCmdFocused, setIsCmdFocused] = useState(false);
  const [timelineVal, setTimelineVal] = useState<number>(100);

  // Keybinding Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const input = document.getElementById('cmdPaletteInput');
        if (input) input.focus();
      } else if (e.key === 'Escape') {
        closePanel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [closePanel]);

  const parsedCmd = useMemo(() => parseCommandQuery(searchQuery), [searchQuery]);

  const selectedContradiction = useMemo<Contradiction | null>(() => {
    if (selectedElement?.type === 'edge' && selectedElement.data) {
      return selectedElement.data as Contradiction;
    }
    if (selectedElement?.type === 'node' && allContradictions.length > 0) {
      const label = selectedElement.data?.label || '';
      return allContradictions.find(c => c.entity.toLowerCase().includes(label.toLowerCase())) || allContradictions[0];
    }
    return null;
  }, [selectedElement, allContradictions]);

  const processedElements = useMemo(() => {
    const hiddenNodeIds = new Set<string>();

    collapsedEntities.forEach(entityId => {
      storeEdges.forEach(edge => {
        if (edge.target === entityId && edge.source !== entityId) {
          hiddenNodeIds.add(edge.source);
        } else if (edge.source === entityId && edge.target !== entityId) {
          hiddenNodeIds.add(edge.target);
        }
      });
    });

    let filteredNodes = storeNodes.filter(node => {
      if (hiddenNodeIds.has(node.id)) return false;
      if (parsedCmd.filterSource && node.type === 'claimNode') {
        const src = (node.data.sourceName || '').toLowerCase();
        if (!src.includes(parsedCmd.filterSource.toLowerCase())) return false;
      }
      return true;
    });

    let filteredEdges = storeEdges.filter(edge => {
      const hasSource = filteredNodes.some(n => n.id === edge.source);
      const hasTarget = filteredNodes.some(n => n.id === edge.target);
      if (!hasSource || !hasTarget) return false;
      if (showOnlyContradictions) return edge.type === 'contradictionEdge';
      return true;
    });

    if (showOnlyContradictions) {
      filteredNodes = filteredNodes.filter(node => {
        if (node.type === 'claimNode') {
          return filteredEdges.some(e => e.source === node.id || e.target === node.id);
        }
        return true;
      });
    }

    const q = parsedCmd.textQuery.toLowerCase().trim();
    const mappedNodes: Node[] = filteredNodes.map(node => {
      const matchesSearch =
        q === '' ||
        node.data.label.toLowerCase().includes(q) ||
        (node.data.sourceName && node.data.sourceName.toLowerCase().includes(q)) ||
        (node.data.value && node.data.value.toLowerCase().includes(q));

      return {
        id: node.id,
        type: node.type,
        data: node.data,
        position: node.position,
        style: {
          // Rule #7: opacity transition for search dimming
          opacity: matchesSearch ? 1 : 0.15,
          transition: 'opacity 200ms ease-out',
        },
      } as Node;
    });

    const mappedEdges: Edge[] = filteredEdges.map(edge => {
      const srcNode = mappedNodes.find(n => n.id === edge.source);
      const tgtNode = mappedNodes.find(n => n.id === edge.target);
      const srcOpacity = (srcNode?.style?.opacity as number) ?? 1;
      const tgtOpacity = (tgtNode?.style?.opacity as number) ?? 1;

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: edge.type === 'contradictionEdge' ? 'contradictionEdge' : undefined,
        data: edge.data,
        style: {
          opacity: srcOpacity < 0.5 || tgtOpacity < 0.5 ? 0.06 : undefined,
          transition: 'opacity 200ms ease-out',
          // Rule #1: consensus edges use a restrained neutral color (no teal hijack)
          ...(edge.type !== 'contradictionEdge' && {
            stroke: 'rgba(71,85,105,0.5)',
            strokeWidth: 1,
          }),
        },
      } as Edge;
    });

    return getLayoutedElements(mappedNodes, mappedEdges, 'LR');
  }, [storeNodes, storeEdges, collapsedEntities, showOnlyContradictions, parsedCmd]);

  useEffect(() => {
    setNodes(processedElements.nodes);
    setEdges(processedElements.edges);
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 300 });
    }, 40);
  }, [processedElements, setNodes, setEdges, fitView]);

  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    await executeStreamQuery(parsedCmd.textQuery || searchQuery);
  };

  const handleNodeClickEvent = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.type === 'entityNode') {
      toggleEntityCollapse(node.id);
    } else {
      selectNode(node.id);
    }
  }, [toggleEntityCollapse, selectNode]);

  const getMiniMapNodeColor = useCallback((node: Node) => {
    // Rule #1: teal for entities, muted for claims
    return node.type === 'entityNode' ? '#14B8A6' : '#334155';
  }, []);

  const formatCategoryLabel = (type: ContradictionCategory) => {
    switch (type) {
      case 'direct_contradiction': return 'Direct Contradiction';
      case 'methodology_mismatch': return 'Methodology Mismatch';
      case 'scope_mismatch': return 'Scope Mismatch';
      case 'stale': return 'Superceded / Stale';
      default: return type;
    }
  };

  return (
    // Rule #3: layout uses consistent spacing scale — 16px (4×4) margins
    <div
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        userSelect: 'none',
        // Rule #1: single background
        backgroundColor: '#070C14',
        // Rule #2: Inter as the UI typeface global
        fontFamily: 'Inter, system-ui, sans-serif',
      }}
    >

      {/* Google Fonts — Inter + JetBrains Mono */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        /* Rule #5: animated underline on links — one signature detail */
        .graph-link {
          position: relative;
          text-decoration: none;
          color: #14B8A6;
        }
        .graph-link::after {
          content: '';
          position: absolute;
          bottom: -1px;
          left: 0;
          width: 0;
          height: 1px;
          background: #14B8A6;
          transition: width 200ms ease-out;
        }
        .graph-link:hover::after { width: 100%; }

        /* Override ReactFlow background / canvas chrome */
        .react-flow__renderer { background: transparent !important; }
      `}</style>

      {/* ── COMMAND PALETTE (TOP CENTER) ─────────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          top: 16,        // Rule #3: 16px
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 50,
          width: '100%',
          maxWidth: 480,
          padding: '0 16px',
        }}
      >
        <form
          onSubmit={handleQuerySubmit}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,              // Rule #3: 8px gap
            padding: '8px 12px', // Rule #3: 8/12px
            borderRadius: 6,
            // Rule #4: no shadow; background shift + border only
            backgroundColor: '#0D1520',
            border: `1px solid ${isCmdFocused ? 'rgba(20,184,166,0.6)' : 'rgba(71,85,105,0.3)'}`,
            // Rule #7: 200ms ease-out
            transition: 'border-color 200ms ease-out',
          }}
        >
          {/* Rule #2: SVG icon instead of emoji, cleaner */}
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0, opacity: 0.4 }}>
            <circle cx="6.5" cy="6.5" r="5" stroke="#94A3B8" strokeWidth="1.5" />
            <path d="M10.5 10.5L14 14" stroke="#94A3B8" strokeWidth="1.5" strokeLinecap="round" />
          </svg>

          <input
            id="cmdPaletteInput"
            type="text"
            placeholder="Search or type source:Reuters…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setIsCmdFocused(true)}
            onBlur={() => setIsCmdFocused(false)}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              // Rule #2: Inter, single size
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 12,
              fontWeight: 400,
              color: '#E2E8F0',
            }}
          />

          {/* Rule #2: weight contrast for the shortcut badge */}
          <kbd
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 9,
              color: '#475569',
              backgroundColor: '#070C14',
              border: '1px solid rgba(71,85,105,0.3)',
              padding: '2px 6px',
              borderRadius: 3,
              flexShrink: 0,
            }}
          >
            ⌘K
          </kbd>

          {/* Rule #1: teal accent ONLY on the primary action button */}
          <button
            type="submit"
            disabled={isStreaming}
            style={{
              padding: '4px 12px',   // Rule #3: 4/12px
              backgroundColor: isStreaming ? 'rgba(20,184,166,0.15)' : '#14B8A6',
              color: isStreaming ? '#14B8A6' : '#070C14',
              border: 'none',
              borderRadius: 4,
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 11,
              fontWeight: 600,
              cursor: isStreaming ? 'default' : 'pointer',
              // Rule #7: 200ms
              transition: 'background-color 200ms ease-out, color 200ms ease-out',
              flexShrink: 0,
            }}
          >
            {isStreaming ? 'Analyzing…' : 'Query'}
          </button>
        </form>

        {/* Progress bar — Rule #7: only when communicating actual state change */}
        {isStreaming && (
          <div
            style={{
              marginTop: 8,
              padding: '8px 12px',
              borderRadius: 5,
              backgroundColor: '#0D1520',
              border: '1px solid rgba(20,184,166,0.2)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: 9,
                color: '#475569',
                marginBottom: 6,
              }}
            >
              <span>{message}</span>
              <span style={{ color: '#14B8A6' }}>{progressPct}%</span>
            </div>
            <div
              style={{
                width: '100%',
                height: 2,
                backgroundColor: '#111920',
                borderRadius: 1,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${progressPct}%`,
                  backgroundColor: '#14B8A6',
                  // Rule #7: purposeful transition
                  transition: 'width 300ms ease-out',
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── QUICK TOGGLES (TOP RIGHT) ─────────────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          top: 16,    // Rule #3: 16px grid
          right: 16,
          zIndex: 40,
          display: 'flex',
          alignItems: 'center',
          padding: '6px 10px',  // Rule #3: 6/10px
          borderRadius: 5,
          backgroundColor: '#0D1520',
          border: '1px solid rgba(71,85,105,0.25)',
        }}
      >
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            cursor: 'pointer',
          }}
        >
          <input
            type="checkbox"
            checked={showOnlyContradictions}
            onChange={(e) => setShowOnlyContradictions(e.target.checked)}
            // Rule #1: danger accent for the contradiction toggle
            style={{ accentColor: '#F87171', cursor: 'pointer' }}
          />
          <span
            style={{
              fontFamily: 'Inter, system-ui, sans-serif',
              fontSize: 11,
              fontWeight: 500,
              color: showOnlyContradictions ? '#F87171' : '#64748B',
              // Rule #7: 200ms
              transition: 'color 200ms ease-out',
            }}
          >
            Conflicts only
          </span>
        </label>
      </div>

      {/* ── REACT FLOW CANVAS ─────────────────────────────────────────────────── */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClickEvent}
        zoomOnScroll={true}
        zoomOnDoubleClick={false}
        panOnScroll={false}
        panOnDrag={true}
        fitView
        style={{ width: '100%', height: '100%' }}
      >
        {/* Rule #4: very faint dot grid — structure implied, not boxed */}
        <Background color="#1E293B" gap={24} size={1} style={{ opacity: 0.4 }} />

        {/* Rule #6: controls aligned bottom-left */}
        <Controls
          showInteractive={false}
          style={{
            bottom: 16,
            left: 16,
          }}
        />

        {/* MiniMap — Rule #1: only two colors used */}
        <MiniMap
          nodeColor={getMiniMapNodeColor}
          nodeStrokeWidth={0}
          nodeBorderRadius={3}
          maskColor="rgba(7,12,20,0.8)"
          style={{
            backgroundColor: '#0D1520',
            border: '1px solid rgba(71,85,105,0.2)',
            bottom: 16,
            right: 16,
            width: 128,
            height: 80,
          }}
        />

        {/* Legend — Rule #6: grid-aligned bottom center; Rule #3: 8px gaps */}
        <Panel position="bottom-center" style={{ marginBottom: 56 }}>
          <div
            style={{
              display: 'flex',
              gap: 16,
              padding: '5px 12px',
              backgroundColor: '#0D1520',
              border: '1px solid rgba(71,85,105,0.2)',
              borderRadius: 20,
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 9,
              color: '#475569',
              alignItems: 'center',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              {/* Rule #1: teal = entity */}
              <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#14B8A6', display: 'inline-block' }} />
              <span>Entity</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              {/* Rule #1: muted slate = claim */}
              <span style={{ width: 6, height: 6, borderRadius: 2, backgroundColor: '#334155', display: 'inline-block' }} />
              <span>Claim</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              {/* Rule #1: coral = conflict only */}
              <span style={{ width: 14, height: 1.5, backgroundColor: '#F87171', display: 'inline-block', borderRadius: 1 }} />
              <span>Conflict</span>
            </div>
          </div>
        </Panel>
      </ReactFlow>

      {/* ── TIMELINE SCRUB BAR (BOTTOM CENTER) ───────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          bottom: 16,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 40,
          width: '100%',
          maxWidth: 360,
          padding: '0 16px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '6px 12px',
            borderRadius: 5,
            backgroundColor: '#0D1520',
            border: '1px solid rgba(71,85,105,0.2)',
          }}
        >
          <span
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 9,
              color: '#334155',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              flexShrink: 0,
            }}
          >
            Timeline
          </span>
          <input
            type="range"
            min="0"
            max="100"
            value={timelineVal}
            onChange={(e) => setTimelineVal(Number(e.target.value))}
            style={{
              flex: 1,
              accentColor: '#14B8A6',
              cursor: 'pointer',
              height: 2,
            }}
          />
          {/* Rule #2: monospace for timestamps */}
          <span
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 9,
              color: '#14B8A6',
              flexShrink: 0,
            }}
          >
            May 2024
          </span>
        </div>
      </div>

      {/* ── SIDE PANEL — Contradiction Detail ─────────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          height: '100%',
          width: '100%',
          maxWidth: 380,
          zIndex: 50,
          backgroundColor: '#0D1520',
          // Rule #4: 1px border — no heavy shadow
          borderLeft: '1px solid rgba(71,85,105,0.2)',
          overflowY: 'auto',
          padding: 24,   // Rule #3: 24px
          // Rule #7: 220ms ease-out slide
          transform: selectedContradiction ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 220ms ease-out',
        }}
      >
        {selectedContradiction && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* Header */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                borderBottom: '1px solid rgba(71,85,105,0.15)',
                paddingBottom: 16,  // Rule #3: 16px
              }}
            >
              <div>
                {/* Rule #1: coral ONLY for contradiction type — danger accent */}
                <span
                  style={{
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: 8,
                    fontWeight: 700,
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    color: '#F87171',
                    border: '1px solid rgba(248,113,113,0.3)',
                    backgroundColor: 'rgba(248,113,113,0.06)',
                    padding: '2px 6px',
                    borderRadius: 3,
                    display: 'inline-block',
                    marginBottom: 8,
                  }}
                >
                  {formatCategoryLabel(selectedContradiction.contradiction_type)}
                </span>
                {/* Rule #2: Inter bold for entity name — h-level element */}
                <h3
                  style={{
                    fontFamily: 'Inter, system-ui, sans-serif',
                    fontWeight: 700,
                    fontSize: 15,
                    color: '#E2E8F0',
                    margin: 0,
                    lineHeight: 1.3,
                  }}
                >
                  {selectedContradiction.entity}
                </h3>
              </div>
              <button
                onClick={() => closePanel()}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#334155',
                  fontSize: 14,
                  cursor: 'pointer',
                  padding: '2px 4px',
                  lineHeight: 1,
                  // Rule #7: 150ms
                  transition: 'color 150ms ease-out',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = '#94A3B8'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = '#334155'; }}
              >
                ✕
              </button>
            </div>

            {/* Claim A vs B — Rule #6: aligned grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {/* Claim A */}
              <div
                style={{
                  padding: 12,   // Rule #3: 12px
                  backgroundColor: '#0A111C',
                  border: '1px solid rgba(71,85,105,0.15)',
                  borderRadius: 4,
                }}
              >
                <div
                  style={{
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: 8,
                    fontWeight: 700,
                    // Rule #1: teal for source A label (entity-side)
                    color: '#14B8A6',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    marginBottom: 6,
                  }}
                >
                  A · {selectedContradiction.source_a?.source_name}
                </div>
                <div
                  style={{
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: 10,
                    fontWeight: 600,
                    color: '#CBD5E1',
                    marginBottom: 6,
                  }}
                >
                  {selectedContradiction.source_a?.claimed_scope?.methodology || 'Reported Claim'}
                </div>
                <p
                  style={{
                    fontFamily: 'Inter, system-ui, sans-serif',
                    fontSize: 10,
                    color: '#475569',
                    lineHeight: 1.5,
                    fontStyle: 'italic',
                    margin: '0 0 8px',
                    overflow: 'hidden',
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                  }}
                >
                  "{selectedContradiction.source_a?.excerpt}"
                </p>
                {selectedContradiction.source_a?.url && (
                  // Rule #5: animated underline link — one deliberate flourish applied consistently
                  <a
                    href={selectedContradiction.source_a.url}
                    target="_blank"
                    rel="noreferrer"
                    className="graph-link"
                    style={{
                      fontFamily: '"JetBrains Mono", monospace',
                      fontSize: 9,
                    }}
                  >
                    ↗ View source
                  </a>
                )}
              </div>

              {/* Claim B */}
              <div
                style={{
                  padding: 12,
                  backgroundColor: '#0A111C',
                  border: '1px solid rgba(71,85,105,0.15)',
                  borderRadius: 4,
                }}
              >
                <div
                  style={{
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: 8,
                    fontWeight: 700,
                    // Rule #1: coral for source B (contradiction side)
                    color: '#F87171',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    marginBottom: 6,
                  }}
                >
                  B · {selectedContradiction.source_b?.source_name}
                </div>
                <div
                  style={{
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: 10,
                    fontWeight: 600,
                    color: '#CBD5E1',
                    marginBottom: 6,
                  }}
                >
                  {selectedContradiction.source_b?.claimed_scope?.methodology || 'Reported Claim'}
                </div>
                <p
                  style={{
                    fontFamily: 'Inter, system-ui, sans-serif',
                    fontSize: 10,
                    color: '#475569',
                    lineHeight: 1.5,
                    fontStyle: 'italic',
                    margin: '0 0 8px',
                    overflow: 'hidden',
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                  }}
                >
                  "{selectedContradiction.source_b?.excerpt}"
                </p>
                {selectedContradiction.source_b?.url && (
                  <a
                    href={selectedContradiction.source_b.url}
                    target="_blank"
                    rel="noreferrer"
                    className="graph-link"
                    style={{
                      fontFamily: '"JetBrains Mono", monospace',
                      fontSize: 9,
                    }}
                  >
                    ↗ View source
                  </a>
                )}
              </div>
            </div>

            {/* AI Reasoning — Rule #4: background shift, not a heavy box */}
            <div
              style={{
                padding: 16,
                backgroundColor: '#0A111C',
                border: '1px solid rgba(71,85,105,0.15)',
                borderRadius: 4,
              }}
            >
              <h4
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  fontSize: 9,
                  fontWeight: 700,
                  // Rule #1: teal for section header (entity/analysis side)
                  color: '#14B8A6',
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  margin: '0 0 8px',
                }}
              >
                Classifier Reasoning
              </h4>
              <p
                style={{
                  fontFamily: 'Inter, system-ui, sans-serif',
                  fontSize: 11,
                  color: '#64748B',
                  lineHeight: 1.6,
                  margin: '0 0 12px',
                }}
              >
                {selectedContradiction.reason}
              </p>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontFamily: '"JetBrains Mono", monospace',
                  fontSize: 9,
                  color: '#334155',
                  paddingTop: 10,
                  borderTop: '1px solid rgba(71,85,105,0.1)',
                }}
              >
                <span>Confidence</span>
                {/* Rule #2: weight contrast makes this number read as "precise" */}
                <span style={{ fontWeight: 700, color: '#CBD5E1', fontSize: 12 }}>
                  {Math.round(selectedContradiction.confidence * 100)}%
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── ERROR TOAST ─────────────────────────────────────────────────────────── */}
      {error && (
        <div
          style={{
            position: 'absolute',
            // Rule #3: 16px grid top, right
            top: 72,
            right: 16,
            zIndex: 50,
            padding: '8px 12px',
            borderRadius: 5,
            backgroundColor: '#0D1520',
            // Rule #1: coral danger only for errors
            border: '1px solid rgba(248,113,113,0.4)',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 10,
            color: '#F87171',
          }}
        >
          {error}
        </div>
      )}

    </div>
  );
};

export const OmniGraph: React.FC = () => {
  return (
    <ReactFlowProvider>
      <GraphCanvas />
    </ReactFlowProvider>
  );
};
