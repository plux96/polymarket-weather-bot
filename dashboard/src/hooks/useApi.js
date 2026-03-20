import { useState, useEffect, useRef, useCallback } from 'react';

const BASE_URL = '';
const POLL_INTERVAL = 15000;

function usePollingFetch(endpoint) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}${endpoint}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (mountedRef.current) {
        setData(json);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message);
        setLoading(false);
      }
    }
  }, [endpoint]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    timerRef.current = setInterval(fetchData, POLL_INTERVAL);
    return () => {
      mountedRef.current = false;
      clearInterval(timerRef.current);
    };
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

export function useStatus()   { return usePollingFetch('/api/status'); }
export function useTrades()   { return usePollingFetch('/api/trades'); }
export function usePnl()      { return usePollingFetch('/api/pnl'); }
export function useCities()   { return usePollingFetch('/api/cities'); }
export function useSignals()  { return usePollingFetch('/api/signals'); }
export function useModels()   { return usePollingFetch('/api/models'); }
export function useActivity() { return usePollingFetch('/api/activity'); }

function usePollingFetchCustom(endpoint, interval) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}${endpoint}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (mountedRef.current) {
        setData(json);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message);
        setLoading(false);
      }
    }
  }, [endpoint]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    timerRef.current = setInterval(fetchData, interval);
    return () => {
      mountedRef.current = false;
      clearInterval(timerRef.current);
    };
  }, [fetchData, interval]);

  return { data, loading, error, refetch: fetchData };
}

export function useInvestment()   { return usePollingFetch('/api/investment'); }
export function useLeaderboard()  { return usePollingFetchCustom('/api/leaderboard', 30000); }
export function useCopySignals()  { return usePollingFetchCustom('/api/copy-signals', 30000); }
