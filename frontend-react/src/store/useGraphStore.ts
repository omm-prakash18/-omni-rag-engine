import { create } from 'zustand';

export interface SourceRef {
  chunk_id: string;
  source_name: string;
  author?: string;
  published_at?: string;
  excerpt: string;
  url?: string;
  sentiment?: number;
  claimed_scope?: {
    date_range?: string;
    geography?: string;
    methodology?: string;
  };
}

export interface Contradiction {
  id: string;
  entity: string;
  metric?: string;
  contradiction_type: 'direct_contradiction' | 'stale' | 'scope_mismatch' | 'methodology_mismatch';
  reason: string;
  confidence: number;
  source_a: SourceRef;
  source_b: SourceRef;
}

export interface GraphNode {
  id: string;
  type: 'entityNode' | 'claimNode';
  data: {
    label: string;
    sourceCount?: number;
    metric?: string;
    sourceName?: string;
    value?: string;
    publishedAt?: string;
    author?: string;
    claimedScope?: {
      date_range?: string;
      geography?: string;
      methodology?: string;
    };
  };
  position: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'contradictionEdge' | 'consensusEdge';
  data?: {
    contradictionId?: string;
    reason?: string;
    confidence?: number;
  };
}

export type LoadingStage = 'idle' | 'reading_sources' | 'mapping_entities' | 'analyzing_consensus' | 'complete';

interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  allContradictions: Contradiction[];
  selectedElement: {
    type: 'node' | 'edge';
    id: string;
    data: any;
  } | null;
  isPanelOpen: boolean;
  timeValue: number; // 0 to 100
  isLoading: boolean;
  loadingStage: LoadingStage;

  // Search and Filter State
  searchQuery: string;
  showOnlyContradictions: boolean;
  selectedSources: string[];
  collapsedEntities: string[]; // List of entity node IDs whose claims are collapsed

  // Actions
  setNodes: (nodes: GraphNode[]) => void;
  setEdges: (edges: GraphEdge[]) => void;
  selectNode: (nodeId: string) => void;
  selectEdge: (edgeId: string) => void;
  closePanel: () => void;
  setTimeValue: (val: number) => void;
  startLoading: () => void;
  setLoadingStage: (stage: LoadingStage) => void;
  stopLoading: () => void;

  // Filter Actions
  setSearchQuery: (query: string) => void;
  setShowOnlyContradictions: (show: boolean) => void;
  toggleSourceFilter: (source: string) => void;
  toggleEntityCollapse: (entityId: string) => void;

  // API Ingestion Layer
  fetchGraphData: (topic: string) => Promise<void>;
}

// Default Mock Fallback Data (matching index.html seeded items)
const MOCK_CONTRADICTIONS: Contradiction[] = [
  {
    id: 'contra_inflation_1',
    entity: 'US Inflation Rate',
    metric: 'CPI year-over-year',
    contradiction_type: 'methodology_mismatch',
    reason: 'Bloomberg Economics uses proprietary spot market rent renewal indexing whereas Reuters uses official BLS lagged survey data.',
    confidence: 0.94,
    source_a: {
      chunk_id: 'c_reuters_1',
      source_name: 'Reuters',
      author: 'Jonathan Cable',
      published_at: '2024-05-15T12:00:00Z',
      excerpt: 'US inflation rate registered a 3.2% year-over-year increase in May, driven by lagged official housing index components.',
      claimed_scope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'BLS Headline CPI (Lagged Survey)',
      }
    },
    source_b: {
      chunk_id: 'c_bloomberg_1',
      source_name: 'Bloomberg',
      author: 'Anna Wong',
      published_at: '2024-05-15T14:30:00Z',
      excerpt: 'Real-time inflation pressures are higher at 3.8% due to active lease pricing models showing rapid rent growth.',
      claimed_scope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'Bloomberg Economics Spot Market Rent Index',
      }
    }
  },
  {
    id: 'contra_inflation_2',
    entity: 'US Inflation Rate',
    metric: 'CPI alternative basket',
    contradiction_type: 'methodology_mismatch',
    reason: 'Reuters claims 3.2% based on standard BLS CPI basket, while AP claims 3.9% due to unweighted chained model adjustments.',
    confidence: 0.88,
    source_a: {
      chunk_id: 'c_reuters_1',
      source_name: 'Reuters',
      author: 'Jonathan Cable',
      published_at: '2024-05-15T12:00:00Z',
      excerpt: 'US inflation rate registered a 3.2% year-over-year increase in May, driven by lagged official housing index components.',
      claimed_scope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'BLS Headline CPI (Lagged Survey)',
      }
    },
    source_b: {
      chunk_id: 'c_ap_1',
      source_name: 'Associated Press',
      author: 'Christopher Rugaber',
      published_at: '2024-05-17T09:15:00Z',
      excerpt: 'An alternative unweighted chained basket analysis places current CPI inflation rate at 3.9%, correcting for regional transportation spikes.',
      claimed_scope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'Unweighted Chained CPI Basket Model',
      }
    }
  }
];

const MOCK_NODES: GraphNode[] = [
  {
    id: 'ent_us_inflation',
    type: 'entityNode',
    data: { label: 'US Inflation Rate', sourceCount: 4, metric: 'CPI & PCE' },
    position: { x: 300, y: 200 }
  },
  {
    id: 'ent_fed_rate',
    type: 'entityNode',
    data: { label: 'Federal Funds Rate', sourceCount: 2, metric: 'Target Range' },
    position: { x: 750, y: 350 }
  },
  {
    id: 'claim_reuters_inf',
    type: 'claimNode',
    data: {
      label: 'Reuters: 3.2%',
      sourceName: 'Reuters',
      value: '3.2%',
      publishedAt: '2024-05-15',
      author: 'Jonathan Cable',
      claimedScope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'BLS Headline CPI (Lagged Survey)'
      }
    },
    position: { x: 100, y: 100 }
  },
  {
    id: 'claim_bloomberg_inf',
    type: 'claimNode',
    data: {
      label: 'Bloomberg: 3.8%',
      sourceName: 'Bloomberg',
      value: '3.8%',
      publishedAt: '2024-05-15',
      author: 'Anna Wong',
      claimedScope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'Bloomberg Economics Spot Rent Index'
      }
    },
    position: { x: 500, y: 80 }
  },
  {
    id: 'claim_ap_inf',
    type: 'claimNode',
    data: {
      label: 'AP: 3.9%',
      sourceName: 'Associated Press',
      value: '3.9%',
      publishedAt: '2024-05-17',
      author: 'Christopher Rugaber',
      claimedScope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'Unweighted Chained CPI Basket Model'
      }
    },
    position: { x: 120, y: 320 }
  },
  {
    id: 'claim_reuters_fed',
    type: 'claimNode',
    data: {
      label: 'Reuters: 5.25%-5.50%',
      sourceName: 'Reuters',
      value: '5.25%-5.50%',
      publishedAt: '2024-05-15',
      claimedScope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'Official FOMC Statement'
      }
    },
    position: { x: 900, y: 220 }
  },
  {
    id: 'claim_cnbc_fed',
    type: 'claimNode',
    data: {
      label: 'CNBC: 5.25%-5.50%',
      sourceName: 'CNBC',
      value: '5.25%-5.50%',
      publishedAt: '2024-05-15',
      claimedScope: {
        date_range: 'May 2024',
        geography: 'US',
        methodology: 'Market Report'
      }
    },
    position: { x: 920, y: 480 }
  }
];

const MOCK_EDGES: GraphEdge[] = [
  { id: 'edge_sup_1', source: 'claim_reuters_inf', target: 'ent_us_inflation', type: 'consensusEdge' },
  { id: 'edge_sup_2', source: 'claim_bloomberg_inf', target: 'ent_us_inflation', type: 'consensusEdge' },
  { id: 'edge_sup_3', source: 'claim_ap_inf', target: 'ent_us_inflation', type: 'consensusEdge' },
  { id: 'edge_sup_4', source: 'claim_reuters_fed', target: 'ent_fed_rate', type: 'consensusEdge' },
  { id: 'edge_sup_5', source: 'claim_cnbc_fed', target: 'ent_fed_rate', type: 'consensusEdge' },
  {
    id: 'edge_contra_1',
    source: 'claim_reuters_inf',
    target: 'claim_bloomberg_inf',
    type: 'contradictionEdge',
    data: {
      contradictionId: 'contra_inflation_1',
      reason: 'Methodology mismatch on housing/shelter indexing.',
      confidence: 0.94
    }
  },
  {
    id: 'edge_contra_2',
    source: 'claim_reuters_inf',
    target: 'claim_ap_inf',
    type: 'contradictionEdge',
    data: {
      contradictionId: 'contra_inflation_2',
      reason: 'Unweighted chained adjustments versus standard CPI weights.',
      confidence: 0.88
    }
  }
];

export const useGraphStore = create<GraphState>((set, get) => ({
  nodes: MOCK_NODES,
  edges: MOCK_EDGES,
  allContradictions: MOCK_CONTRADICTIONS,
  selectedElement: null,
  isPanelOpen: false,
  timeValue: 100,
  isLoading: false,
  loadingStage: 'idle',

  // Search and Filter State
  searchQuery: '',
  showOnlyContradictions: false,
  selectedSources: [],
  collapsedEntities: [],

  // Actions
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  selectNode: (nodeId) => {
    const node = get().nodes.find(n => n.id === nodeId);
    if (node) {
      set({
        selectedElement: { type: 'node', id: nodeId, data: node.data },
        isPanelOpen: true
      });
    }
  },

  selectEdge: (edgeId) => {
    const edge = get().edges.find(e => e.id === edgeId);
    if (edge && edge.type === 'contradictionEdge' && edge.data?.contradictionId) {
      const contra = get().allContradictions.find(c => c.id === edge.data?.contradictionId);
      if (contra) {
        set({
          selectedElement: { type: 'edge', id: edgeId, data: contra },
          isPanelOpen: true
        });
      }
    }
  },

  closePanel: () => set({ isPanelOpen: false, selectedElement: null }),

  setTimeValue: (val) => {
    set({ timeValue: val });
  },

  startLoading: () => set({ isLoading: true, loadingStage: 'reading_sources' }),
  setLoadingStage: (stage) => set({ loadingStage: stage }),
  stopLoading: () => set({ isLoading: false, loadingStage: 'complete' }),

  setSearchQuery: (query) => set({ searchQuery: query }),
  setShowOnlyContradictions: (show) => set({ showOnlyContradictions: show }),
  
  toggleSourceFilter: (source) => {
    const active = get().selectedSources;
    if (active.includes(source)) {
      set({ selectedSources: active.filter(s => s !== source) });
    } else {
      set({ selectedSources: [...active, source] });
    }
  },

  toggleEntityCollapse: (entityId) => {
    const collapsed = get().collapsedEntities;
    if (collapsed.includes(entityId)) {
      set({ collapsedEntities: collapsed.filter(id => id !== entityId) });
    } else {
      set({ collapsedEntities: [...collapsed, entityId] });
    }
  },

  // API Integration Layer
  fetchGraphData: async (topic: string) => {
    set({ isLoading: true, loadingStage: 'reading_sources' });
    
    try {
      // Set to API Host (fallback to localhost:8000 for standard setup)
      const host = window.location.port === '8000' ? window.location.origin : 'http://localhost:8000';
      
      const response = await fetch(`${host}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: topic, top_k: 10 }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      set({ loadingStage: 'mapping_entities' });
      const resData = await response.json();

      const rawNodes = resData.graph?.nodes || [];
      const rawEdges = resData.graph?.edges || [];
      const contradictions = resData.contradictions || [];

      // Map backend GraphNode schema to React Flow GraphNode structures
      const mappedNodes: GraphNode[] = rawNodes.map((n: any) => {
        // Map backend types ("entity", "claim", "source") to React Flow Node types
        const type = n.type === 'entity' ? 'entityNode' : 'claimNode';
        
        return {
          id: n.id,
          type,
          data: {
            label: n.label,
            sourceCount: n.data?.sourceCount,
            metric: n.data?.metric,
            sourceName: n.data?.sourceName || (n.type === 'source' ? n.label : undefined),
            value: n.data?.value,
            publishedAt: n.data?.publishedAt,
            author: n.data?.author,
            claimedScope: n.data?.claimedScope,
          },
          // Positional defaults (Dagre layout will overwrite this automatically in UI)
          position: { x: Math.random() * 200 + 100, y: Math.random() * 200 + 100 },
        };
      });

      // Map backend GraphEdge schema to React Flow GraphEdge structures
      const mappedEdges: GraphEdge[] = rawEdges.map((e: any) => {
        // Map backend edge types to custom React Flow edges
        const isContra = e.type === 'CONTRADICTS' || e.type.includes('CONTRADICTION') ||
                         e.type === 'METHODOLOGY_MISMATCH' || e.type === 'SCOPE_MISMATCH';
        const type = isContra ? 'contradictionEdge' : 'consensusEdge';

        return {
          id: e.id,
          source: e.source,
          target: e.target,
          type,
          data: {
            contradictionId: e.data?.type ? e.id.replace('e_contra_', 'contra_') : undefined,
            reason: e.data?.reason,
            confidence: e.data?.confidence,
          },
        };
      });

      // Update store state gracefully preserving zoom/pan position
      set({
        nodes: mappedNodes,
        edges: mappedEdges,
        allContradictions: contradictions,
        isLoading: false,
        loadingStage: 'complete',
      });

    } catch (error) {
      console.error('Failed to fetch real-time graph data from backend API:', error);
      
      // Graceful fallback to static seeds when backend query fails or offline
      set({ loadingStage: 'complete', isLoading: false });
      
      // Pre-filter MOCK nodes based on query topic keywords
      const queryLow = topic.toLowerCase();
      if (queryLow.includes('fed') || queryLow.includes('interest')) {
        set({
          nodes: MOCK_NODES.filter(n => n.id.includes('fed')),
          edges: MOCK_EDGES.filter(e => e.source.includes('fed') || e.target.includes('fed')),
          allContradictions: []
        });
      } else if (queryLow.includes('inflation') || queryLow.includes('cpi')) {
        set({
          nodes: MOCK_NODES.filter(n => !n.id.includes('fed')),
          edges: MOCK_EDGES.filter(e => !e.source.includes('fed') && !e.target.includes('fed')),
          allContradictions: MOCK_CONTRADICTIONS
        });
      } else {
        set({
          nodes: MOCK_NODES,
          edges: MOCK_EDGES,
          allContradictions: MOCK_CONTRADICTIONS
        });
      }
    }
  }
}));
