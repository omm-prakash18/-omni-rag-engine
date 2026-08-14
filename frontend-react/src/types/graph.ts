export type ContradictionCategory = 
  | 'direct_contradiction' 
  | 'stale' 
  | 'scope_mismatch' 
  | 'methodology_mismatch';

export interface ClaimScope {
  date_range?: string;
  geography?: string;
  methodology?: string;
}

export interface SourceArticle {
  source_name: string;
  author?: string;
  title?: string;
  url?: string;
  published_at?: string;
  sentiment?: number;
  excerpt?: string;
  claimed_scope?: ClaimScope;
}

export interface Contradiction {
  id: string;
  entity: string;
  metric: string;
  contradiction_type: ContradictionCategory;
  reason: string;
  confidence: number;
  source_a: SourceArticle;
  source_b: SourceArticle;
}

export interface EntityNodeData {
  label: string;
  metric?: string;
  sourceCount?: number;
  isCollapsed?: boolean;
}

export interface ClaimNodeData {
  label: string;
  sourceName?: string;
  value?: string;
  publishedAt?: string;
  author?: string;
}

export interface ContradictionEdgeData {
  reason?: string;
  confidence?: number;
  type?: ContradictionCategory;
  contradictionId?: string;
}

export interface ConsensusEdgeData {
  value?: string;
}

export interface GraphPayload {
  nodes: Array<{
    id: string;
    label: string;
    type: 'entity' | 'source' | 'claim';
    data?: Record<string, any>;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    type: 'SUPPORTS' | 'CONTRADICTS' | string;
    data?: Record<string, any>;
  }>;
}

export interface QueryRequest {
  query: string;
  top_k?: number;
}

export interface QueryResponse {
  query: string;
  contradictions: Contradiction[];
  graph: GraphPayload;
  steps: string[];
  cached: boolean;
  demo_mode?: boolean;
}

export type StreamStage = 
  | 'idle'
  | 'connecting'
  | 'vector_search'
  | 'crag_evaluation'
  | 'graph_synthesis'
  | 'classification'
  | 'complete'
  | 'error';

export interface StreamProgressEvent {
  type: 'stage' | 'chunk' | 'contradiction' | 'complete' | 'error';
  stage?: StreamStage;
  message?: string;
  progressPct?: number;
  data?: any;
}
