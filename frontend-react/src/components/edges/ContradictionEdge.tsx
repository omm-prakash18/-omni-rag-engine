import React from 'react';
import { EdgeLabelRenderer, EdgeProps, getBezierPath } from '@xyflow/react';
import { useGraphStore } from '../../store/useGraphStore';

export const ContradictionEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const selectEdge = useGraphStore(state => state.selectEdge);

  return (
    <>
      {/*
        Rule #1: one accent color — coral #F87171 used ONLY for conflict.
        Rule #5: dashed animation is the one signature flourish; kept only here.
        Rule #7: dash animation ~1.4s, purposeful (communicates "live conflict").
      */}
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        fill="none"
        stroke="#F87171"
        strokeWidth={1.5}
        strokeDasharray="6 4"
        style={{
          ...style,
          animation: 'contradictionDash 1.4s linear infinite',
        }}
        markerEnd={markerEnd}
      />

      {/* Rule #5: one deliberate flourish — the CONFLICT badge, minimal */}
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
        >
          <button
            onClick={() => selectEdge(id)}
            style={{
              // Rule #3: 4px/8px spacing only
              padding: '2px 7px',
              // Rule #4: bg-shift approach, not heavy shadow
              backgroundColor: '#070C14',
              border: '1px solid rgba(248,113,113,0.5)',
              borderRadius: 3,
              // Rule #2: monospace for badges/labels that are "precise"
              fontFamily: '"JetBrains Mono", "Fira Code", monospace',
              fontSize: 8,
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: '#F87171',
              cursor: 'pointer',
              // Rule #7: 200ms ease-out
              transition: 'background-color 200ms ease-out, border-color 200ms ease-out',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(248,113,113,0.08)';
              (e.currentTarget as HTMLButtonElement).style.borderColor = '#F87171';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#070C14';
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(248,113,113,0.5)';
            }}
          >
            CONFLICT
          </button>
        </div>
      </EdgeLabelRenderer>

      <style>{`
        @keyframes contradictionDash {
          to { stroke-dashoffset: -20; }
        }
      `}</style>
    </>
  );
};
