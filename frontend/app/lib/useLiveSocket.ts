"use client";
import { useEffect, useRef, useState } from "react";
import { WS_URL } from "./api";

export interface LiveMessage {
  type: "price" | "signal";
  [key: string]: any;
}

/**
 * Connects to the backend's /ws/live endpoint and keeps the latest price
 * tick and latest signal in state, with automatic reconnect on drop.
 */
export function useLiveSocket() {
  const [lastPrice, setLastPrice] = useState<LiveMessage | null>(null);
  const [lastSignal, setLastSignal] = useState<LiveMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(`${WS_URL}/ws/live`);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        try {
          const data: LiveMessage = JSON.parse(event.data);
          if (data.type === "price") setLastPrice(data);
          if (data.type === "signal") setLastSignal(data);
        } catch {
          /* ignore malformed message */
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return { lastPrice, lastSignal, connected };
}
