/**
 * useDashboard
 * Single shared hook that polls all Flask /api/* endpoints.
 * Import this in any React section to get live bot data.
 *
 * Usage:
 *   import { useDashboard } from '@/hooks/useDashboard'
 *   const { portfolio, positions, stats, scanState } = useDashboard()
 */
import { useState, useEffect, useCallback } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export interface Portfolio {
  equity: number;
  cash: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  returns_pct: number;
  num_positions: number;
  bot_running: boolean;
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  pnl_pct: number;
  stop_loss: number | null;
  take_profit: number | null;
  trailing_stop: number | null;
}

export interface Trade {
  id: number;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  pnl: number;
  timestamp: string;
}

export interface Stats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  best_trade: number;
  worst_trade: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
}

export interface ScannedStock {
  symbol: string;
  signal: "BUY" | "SELL" | "HOLD";
  strategy: string;
  condition: string;
  strength: number | string;
  rsi: number | null;
}

export interface ScanState {
  scanning: boolean;
  last_scan: string | null;
  liquid_count: number;
  opp_count: number;
  stocks: ScannedStock[];
}

// ── Default values (shown before first fetch) ────────────────────────────────
const DEFAULT_PORTFOLIO: Portfolio = {
  equity: 0, cash: 0, unrealized_pnl: 0,
  realized_pnl: 0, total_pnl: 0,
  returns_pct: 0, num_positions: 0, bot_running: false,
};

const DEFAULT_SCAN: ScanState = {
  scanning: false, last_scan: null,
  liquid_count: 0, opp_count: 0, stocks: [],
};

const DEFAULT_STATS: Stats = {
  total_trades: 0, winning_trades: 0, losing_trades: 0,
  win_rate: 0, best_trade: 0, worst_trade: 0,
  avg_win: 0, avg_loss: 0, profit_factor: 0,
};

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useDashboard(refreshMs = 5000) {
  const [portfolio,  setPortfolio]  = useState<Portfolio>(DEFAULT_PORTFOLIO);
  const [positions,  setPositions]  = useState<Position[]>([]);
  const [trades,     setTrades]     = useState<Trade[]>([]);
  const [stats,      setStats]      = useState<Stats>(DEFAULT_STATS);
  const [scanState,  setScanState]  = useState<ScanState>(DEFAULT_SCAN);
  const [connected,  setConnected]  = useState(false);
  const [loading,    setLoading]    = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [p, pos, t, s, sc] = await Promise.all([
        fetch("/api/portfolio").then(r => r.json()),
        fetch("/api/positions").then(r => r.json()),
        fetch("/api/trades?limit=20").then(r => r.json()),
        fetch("/api/stats").then(r => r.json()),
        fetch("/api/scan_state").then(r => r.json()),
      ]);
      setPortfolio(p);
      setPositions(pos);
      setTrades(t);
      setStats(s);
      setScanState(sc);
      setConnected(true);
    } catch {
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, refreshMs);
    return () => clearInterval(id);
  }, [fetchAll, refreshMs]);

  // ── Actions ─────────────────────────────────────────────────────────────────
  const toggleBot = async () => {
    await fetch("/api/toggle_bot", { method: "POST" });
    fetchAll();
  };

  const killSwitch = async () => {
    const r = await fetch("/api/kill_switch", { method: "POST" }).then(x => x.json());
    fetchAll();
    return r;
  };

  return {
    portfolio, positions, trades, stats, scanState,
    connected, loading,
    toggleBot, killSwitch, refresh: fetchAll,
  };
}
