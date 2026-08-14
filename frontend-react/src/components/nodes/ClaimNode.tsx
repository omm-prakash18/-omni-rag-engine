import React, { useState } from 'react';
import { Handle, Position } from '@xyflow/react';

interface ClaimNodeProps {
  data: {
    label: string;
    sourceName?: string;
    value?: string;
    publishedAt?: string;
    author?: string;
  };
}

export const ClaimNode: React.FC<ClaimNodeProps> = ({ data }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      style={{
        // Rule #3: spacing on 4/8/12px scale
        padding: '10px 12px',
        // Rule #4: background-shift defines structure, not shadow
        backgroundColor: isHovered ? '#111920' : '#0D1520',
        border: `1px solid ${isHovered ? 'rgba(148,163,184,0.35)' : 'rgba(148,163,184,0.12)'}`,
        borderRadius: 5,
        minWidth: 170,
        textAlign: 'left',
        // Rule #7: 200ms ease-out only
        transition: 'border-color 200ms ease-out, background-color 200ms ease-out',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Rule #2: monospace for source name (precise/data), size contrast for hierarchy */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span
            style={{
              fontFamily: '"JetBrains Mono", "Fira Code", monospace',
              fontSize: 9,
              fontWeight: 600,
              color: '#475569',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            {data.sourceName || 'Source'}
          </span>
          {data.publishedAt && (
            <span
              style={{
                fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                fontSize: 9,
                color: '#334155',
              }}
            >
              {data.publishedAt.slice(0, 10)}
            </span>
          )}
        </div>

        {/* Rule #2: Inter semibold for the key claim value — size hierarchy */}
        <div
          style={{
            fontFamily: 'Inter, system-ui, sans-serif',
            fontSize: 11,
            fontWeight: 600,
            color: '#E2E8F0',
            lineHeight: 1.4,
            // Rule #3: 4px margin
            margin: '4px 0',
          }}
        >
          {data.value}
        </div>

        {data.author && (
          <span
            style={{
              fontFamily: '"JetBrains Mono", "Fira Code", monospace',
              fontSize: 9,
              color: '#334155',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {data.author}
          </span>
        )}
      </div>

      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
};
