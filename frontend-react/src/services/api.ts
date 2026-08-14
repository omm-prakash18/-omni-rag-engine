import { QueryRequest, QueryResponse } from '../types/graph';

const API_BASE_URL = 'http://127.0.0.1:8000';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Perform POST /query call to FastAPI backend
 */
export async function fetchGraphQuery(
  query: string, 
  top_k: number = 10
): Promise<QueryResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, top_k } as QueryRequest),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new ApiError(
        errorText || `Backend returned status ${response.status}`,
        response.status
      );
    }

    const data: QueryResponse = await response.json();
    return data;
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      err.message || 'Failed to connect to Omni-Perspective backend server',
      500
    );
  }
}

/**
 * Command-palette parser to split raw search queries from command tags.
 * Example: "source:Reuters inflation rate" -> { filterSource: "Reuters", textQuery: "inflation rate" }
 */
export function parseCommandQuery(rawInput: string) {
  let filterSource: string | null = null;
  let filterType: string | null = null;
  let cleanQuery = rawInput;

  const sourceMatch = rawInput.match(/source:(\w+)/i);
  if (sourceMatch) {
    filterSource = sourceMatch[1];
    cleanQuery = cleanQuery.replace(sourceMatch[0], '').trim();
  }

  const typeMatch = rawInput.match(/type:(\w+)/i);
  if (typeMatch) {
    filterType = typeMatch[1];
    cleanQuery = cleanQuery.replace(typeMatch[0], '').trim();
  }

  return {
    filterSource,
    filterType,
    textQuery: cleanQuery,
  };
}
