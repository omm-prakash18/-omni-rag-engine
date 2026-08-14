import { useState, useEffect, useCallback, useRef } from 'react';
import { StreamStage, StreamProgressEvent, QueryResponse } from '../types/graph';
import { fetchGraphQuery } from '../services/api';

const WS_BASE_URL = 'ws://127.0.0.1:8000/ws/query';

interface UseGraphStreamReturn {
  stage: StreamStage;
  progressPct: number;
  message: string;
  isStreaming: boolean;
  error: string | null;
  executeStreamQuery: (query: string) => Promise<QueryResponse | null>;
  cancelStream: () => void;
}

export function useGraphStream(): UseGraphStreamReturn {
  const [stage, setStage] = useState<StreamStage>('idle');
  const [progressPct, setProgressPct] = useState<number>(0);
  const [message, setMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);

  const cancelStream = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setIsStreaming(false);
    setStage('idle');
    setProgressPct(0);
  }, []);

  const executeStreamQuery = useCallback(async (query: string): Promise<QueryResponse | null> => {
    cancelStream();
    setError(null);
    setIsStreaming(true);
    setStage('connecting');
    setProgressPct(10);
    setMessage('Connecting to pipeline...');

    return new Promise((resolve) => {
      let isResolved = false;

      // Fallback REST execution function
      const fallbackToRest = async (reason: string) => {
        if (isResolved) return;
        isResolved = true;
        setMessage(`Running REST fallback (${reason})...`);
        setStage('vector_search');
        setProgressPct(40);

        try {
          const res = await fetchGraphQuery(query);
          setStage('complete');
          setProgressPct(100);
          setMessage('Pipeline execution complete');
          setIsStreaming(false);
          resolve(res);
        } catch (err: any) {
          setStage('error');
          setError(err.message || 'Pipeline execution failed');
          setIsStreaming(false);
          resolve(null);
        }
      };

      try {
        const ws = new WebSocket(WS_BASE_URL);
        socketRef.current = ws;

        ws.onopen = () => {
          setStage('vector_search');
          setProgressPct(25);
          setMessage('Query submitted to agent pipeline');
          ws.send(JSON.stringify({ query }));
        };

        ws.onmessage = (event) => {
          try {
            const data: StreamProgressEvent = JSON.parse(event.data);

            if (data.stage) setStage(data.stage);
            if (data.progressPct !== undefined) setProgressPct(data.progressPct);
            if (data.message) setMessage(data.message);

            if (data.type === 'complete' && data.data) {
              isResolved = true;
              setStage('complete');
              setProgressPct(100);
              setIsStreaming(false);
              ws.close();
              resolve(data.data as QueryResponse);
            }
          } catch (e) {
            // Ignore parse issues or treat raw payload as completion
          }
        };

        ws.onerror = () => {
          fallbackToRest('WebSocket unavailable');
        };

        ws.onclose = () => {
          if (!isResolved) {
            fallbackToRest('Socket closed unexpectedly');
          }
        };

        // Safety timeout of 12 seconds
        setTimeout(() => {
          if (!isResolved) {
            fallbackToRest('Connection timeout');
          }
        }, 12000);

      } catch (err) {
        fallbackToRest('WebSocket init error');
      }
    });
  }, [cancelStream]);

  useEffect(() => {
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  return {
    stage,
    progressPct,
    message,
    isStreaming,
    error,
    executeStreamQuery,
    cancelStream,
  };
}
