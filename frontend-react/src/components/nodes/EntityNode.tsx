import React, { useState } from 'react';
import { Handle, Position } from '@xyflow/react';

interface EntityNodeProps {
  data: {
    label: string;
    sourceCount?: number;
    metric?: string;
    isCollapsed?: boolean;
  };
}

export const EntityNode: React.FC<EntityNodeProps> = ({ data }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className="relative text-center select-none cursor-pointer"
      style={{
        // Rule #3: spacing scale — 12px / 10px
        padding: '10px 14px',
        // Rule #4: 1px border, background shift — no shadow unless hovered
        backgroundColor: isHovered ? '#111920' : '#0D1520',
        border: `1px solid ${isHovered ? '#14B8A6' : 'rgba(20,184,166,0.18)'}`,
        borderRadius: 6,
        minWidth: 160,
        // Rule #7: 200ms ease-out — fast, purposeful
        transition: 'border-color 200ms ease-out, background-color 200ms ease-out',
        // Rule #5: one signature detail — the teal left-bar accent
        boxShadow: isHovered ? 'inset 3px 0 0 #14B8A6' : 'inset 3px 0 0 rgba(20,184,166,0.25)',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        {/* Rule #2: grotesk for UI labels, weight for hierarchy */}
        <h4
          style={{
            fontFamily: 'Inter, system-ui, sans-serif',
            fontWeight: 600,
            fontSize: 11,
            letterSpacing: '-0.01em',
            color: '#F1F5F9',
            margin: 0,
          }}
        >
          {data.label}
        </h4>

        {data.isCollapsed && (
          <span
            style={{
              fontFamily: '"JetBrains Mono", "Fira Code", monospace',
              fontSize: 9,
              color: '#64748B',
              backgroundColor: '#070C14',
              border: '1px solid rgba(100,116,139,0.2)',
              padding: '1px 5px',
              borderRadius: 3,
            }}
          >
            +claims
          </span>
        )}
      </div>

      {data.metric && (
        <div
          style={{
            // Rule #2: monospace for data values
            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
            fontSize: 9,
            color: '#475569',
            marginTop: 6,
            paddingTop: 6,
            borderTop: '1px solid rgba(100,116,139,0.12)',
            textAlign: 'left',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.metric}
        </div>
      )}

      {/* Rule #5: one deliberate flourish — source count tooltip */}
      {isHovered && data.sourceCount !== undefined && (
        <div
          style={{
            position: 'absolute',
            top: -28,
            left: '50%',
            transform: 'translateX(-50%)',
            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
            fontSize: 9,
            color: '#14B8A6',
            backgroundColor: '#070C14',
            border: '1px solid rgba(20,184,166,0.4)',
            padding: '2px 8px',
            borderRadius: 3,
            whiteSpace: 'nowrap',
            zIndex: 50,
            // Rule #7: appear fast
            animation: 'none',
          }}
        >
          {data.sourceCount} sources
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
};
