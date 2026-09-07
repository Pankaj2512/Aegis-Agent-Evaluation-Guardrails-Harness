"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { api } from "@/lib/api";

type ObservabilityListener = (event: Record<string, unknown>) => void;

/**
 * UI-facing stream state. Distinct from the raw socket state: `connecting`
 * covers both the first attempt and any short reconnect, so surfaces never
 * raise an "offline / values may be stale" alarm for a stream that is simply
 * still handshaking.
 */
export type ObservabilityStreamStatus = "connecting" | "live" | "offline";

type ObservabilityStreamContextValue = {
  connected: boolean;
  status: ObservabilityStreamStatus;
  subscribe: (listener: ObservabilityListener) => () => void;
};

const ObservabilityStreamContext = createContext<ObservabilityStreamContextValue | null>(
  null
);

const TERMINAL_EVENTS = new Set(["run_completed", "run_failed", "run_cancelled"]);

/** Grace before the first connect attempt is called a failure. */
const CONNECTING_GRACE_MS = 5000;
/** Sustained-disconnect window once we've been live — the reconnect backoff
 *  tops out at 10s, so a flapping stream never surfaces to the user. */
const OFFLINE_DEBOUNCE_MS = 10000;

export function ObservabilityStreamProvider({ children }: { children: React.ReactNode }) {
  const listeners = useRef(new Set<ObservabilityListener>());
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<ObservabilityStreamStatus>("connecting");
  const reconnectAttempts = useRef(0);
  const sourceRef = useRef<{ close: () => void } | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const offlineTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const everLiveRef = useRef(false);
  const closedRef = useRef(false);

  const clearOfflineTimer = useCallback(() => {
    if (offlineTimerRef.current) {
      clearTimeout(offlineTimerRef.current);
      offlineTimerRef.current = null;
    }
  }, []);

  /** Start (or keep) the countdown to "offline". Re-entrant: an already
   *  running countdown is never restarted, so repeated retry failures still
   *  resolve to offline on schedule. */
  const scheduleOffline = useCallback(() => {
    if (offlineTimerRef.current) return;
    offlineTimerRef.current = setTimeout(
      () => {
        offlineTimerRef.current = null;
        setStatus("offline");
      },
      everLiveRef.current ? OFFLINE_DEBOUNCE_MS : CONNECTING_GRACE_MS
    );
  }, []);

  const markLive = useCallback(() => {
    everLiveRef.current = true;
    reconnectAttempts.current = 0;
    clearOfflineTimer();
    setConnected(true);
    setStatus("live");
  }, [clearOfflineTimer]);

  const disconnect = useCallback(() => {
    closedRef.current = true;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    clearOfflineTimer();
    sourceRef.current?.close();
    sourceRef.current = null;
    setConnected(false);
    // Teardown is deliberate (last subscriber left / unmount) — that isn't an
    // outage, so the next mount starts from "connecting", not "offline".
    setStatus("connecting");
  }, [clearOfflineTimer]);

  const connect = useCallback(() => {
    if (closedRef.current || sourceRef.current) return;
    closedRef.current = false;
    scheduleOffline();
    sourceRef.current = api.streamObservability(
      (event) => {
        markLive();
        listeners.current.forEach((listener) => listener(event));
      },
      () => {
        setConnected(false);
        sourceRef.current?.close();
        sourceRef.current = null;
        if (closedRef.current || listeners.current.size === 0) return;
        scheduleOffline();
        reconnectAttempts.current += 1;
        reconnectTimerRef.current = setTimeout(
          connect,
          Math.min(1000 * reconnectAttempts.current, 10000)
        );
      },
      () => {
        // Connection is open as soon as the response is OK — don't wait for
        // the first heartbeat (up to 30s later) to show "Live".
        markLive();
      }
    );
  }, [markLive, scheduleOffline]);

  const subscribe = useCallback(
    (listener: ObservabilityListener) => {
      listeners.current.add(listener);
      if (listeners.current.size === 1) {
        closedRef.current = false;
        connect();
      }
      return () => {
        listeners.current.delete(listener);
        if (listeners.current.size === 0) {
          disconnect();
        }
      };
    },
    [connect, disconnect]
  );

  useEffect(() => () => disconnect(), [disconnect]);

  return (
    <ObservabilityStreamContext.Provider value={{ connected, status, subscribe }}>
      {children}
    </ObservabilityStreamContext.Provider>
  );
}

export function useObservabilityStream() {
  const ctx = useContext(ObservabilityStreamContext);
  if (!ctx) {
    throw new Error("useObservabilityStream must be used within ObservabilityStreamProvider");
  }
  return ctx;
}

export function isTerminalObservabilityEvent(type: unknown): boolean {
  return typeof type === "string" && TERMINAL_EVENTS.has(type);
}