/**
 * LiveDashboard section
 * Embeds the Flask dashboard inside the React website via iframe.
 * The "Launch Full Dashboard" button opens it in a new tab.
 *
 * Place in App.tsx as: <LiveDashboard />
 */
import React, { useState } from "react";
import { useDashboard } from "@/hooks/useDashboard";

const INR = (v: number) =>
  "₹" + Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const PCT = (v: number) => `${v > 0 ? "+" : ""}${Number(v).toFixed(2)}%`;

export default function LiveDashboard() {
  const { portfolio, positions, stats, scanState, connected, loading, toggleBot, killSwitch } =
    useDashboard(5000);
  const [killing, setKilling] = useState(false);

  const handleKill = async () => {
    if (!confirm("Close ALL open positions immediately?")) return;
    setKilling(true);
    const r = await killSwitch();
    setKilling(false);
    alert(r.message || r.error || "Done");
  };

  return (
    <section id="live-dashboard" className="bg-[#0d1117] py-20 px-4">
      <div className="max-w-7xl mx-auto">

        {/* Section Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 bg-[#161b22] border border-[#30363d] rounded-full px-4 py-1 mb-4">
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-[#00e5a0] animate-pulse" : "bg-[#f85149]"}`}/>
            <span className="text-xs font-semibold text-[#8b949e] uppercase tracking-widest">
              {connected ? "Live · Connected to Bot" : loading ? "Connecting..." : "Bot Offline"}
            </span>
          </div>
          <h2 className="text-4xl font-bold text-[#e6edf3] mb-3">
            Live Trading <span className="text-[#00e5a0]">Dashboard</span>
          </h2>
          <p className="text-[#8b949e] max-w-xl mx-auto text-sm">
            Real-time data streamed directly from your running bot.
          </p>
        </div>

        {/* Stats Strip */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
          {[
            { label: "Total Equity",    val: INR(portfolio.equity),          sub: PCT(portfolio.returns_pct), subColor: portfolio.returns_pct >= 0 ? "#00e5a0" : "#f85149" },
            { label: "Cash Available",  val: INR(portfolio.cash),            sub: null, subColor: "" },
            { label: "Unrealized P&L",  val: INR(portfolio.unrealized_pnl),  sub: null, subColor: portfolio.unrealized_pnl >= 0 ? "#00e5a0" : "#f85149" },
            { label: "Realized P&L",    val: INR(portfolio.realized_pnl),    sub: null, subColor: portfolio.realized_pnl >= 0 ? "#00e5a0" : "#f85149" },
            { label: "Open Positions",  val: String(portfolio.num_positions), sub: null, subColor: "" },
          ].map((c, i) => (
            <div key={i} className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
              <div className="text-[10px] text-[#8b949e] uppercase tracking-wider mb-1">{c.label}</div>
              <div className="text-xl font-bold text-[#e6edf3] font-mono">{loading ? "—" : c.val}</div>
              {c.sub && !loading && (
                <div className="text-xs mt-1" style={{ color: c.subColor }}>{c.sub}</div>
              )}
            </div>
          ))}
        </div>

        {/* Main 2-col: Positions + Scanner */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">

          {/* Open Positions */}
          <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#30363d]">
              <span className="text-xs font-bold uppercase tracking-wider text-[#e6edf3]">📊 Open Positions</span>
              <span className="text-xs text-[#8b949e]">{positions.length} active</span>
            </div>
            <div className="overflow-auto max-h-60">
              {positions.length === 0 ? (
                <div className="text-center text-[#8b949e] text-sm py-8">No open positions</div>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[#30363d]">
                      {["Symbol","Qty","Avg","LTP","P&L"].map(h => (
                        <th key={h} className="text-left px-3 py-2 text-[#8b949e] uppercase text-[10px] tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map(p => (
                      <tr key={p.symbol} className="border-b border-[#30363d]/40 hover:bg-[#1c2230]">
                        <td className="px-3 py-2 font-bold text-[#e6edf3]">{p.symbol}</td>
                        <td className="px-3 py-2 text-[#8b949e]">{p.quantity}</td>
                        <td className="px-3 py-2 font-mono text-[#8b949e]">{INR(p.avg_price)}</td>
                        <td className="px-3 py-2 font-mono text-[#e6edf3]">{INR(p.current_price)}</td>
                        <td className="px-3 py-2 font-mono font-bold"
                            style={{ color: p.unrealized_pnl >= 0 ? "#00e5a0" : "#f85149" }}>
                          {INR(p.unrealized_pnl)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Live Scanner */}
          <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#30363d]">
              <span className="text-xs font-bold uppercase tracking-wider text-[#e6edf3]">
                {scanState.scanning
                  ? <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-[#e3b341] animate-pulse inline-block"/>Scanning...</span>
                  : "🔍 Market Scanner"}
              </span>
              <span className="text-xs text-[#8b949e]">
                {scanState.last_scan ? scanState.last_scan : "—"}
              </span>
            </div>
            <div className="overflow-auto max-h-60">
              {scanState.stocks.length === 0 ? (
                <div className="text-center text-[#8b949e] text-sm py-8">Waiting for next scan cycle...</div>
              ) : (
                <div className="grid grid-cols-2 gap-2 p-3">
                  {scanState.stocks.map(s => {
                    const col = { VWAP_MOMENTUM:"#00e5a0", EMA_CROSSOVER:"#0ea5e9", SUPERTREND:"#a78bfa",
                      BOLLINGER_REVERSAL:"#f59e0b", RSI_REVERSAL:"#fb923c", MACD_MOMENTUM:"#38bdf8",
                      VOLUME_BREAKOUT:"#4ade80", ATR_BREAKOUT:"#f87171" }[s.strategy] || "#8b949e";
                    const sigCol = s.signal === "BUY" ? "#00e5a0" : s.signal === "SELL" ? "#f85149" : "#8b949e";
                    return (
                      <div key={s.symbol} className="bg-[#1c2230] rounded-lg p-2 border border-[#30363d]"
                           style={{ borderTopColor: col, borderTopWidth: 2 }}>
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[11px] text-[#e6edf3]">{s.symbol}</span>
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                                style={{ color: sigCol, background: sigCol + "20" }}>{s.signal}</span>
                        </div>
                        <div className="text-[9px] mt-1" style={{ color: col }}>{s.strategy}</div>
                        <div className="text-[9px] text-[#8b949e] mt-0.5">{s.condition}</div>
                        {s.rsi != null && <div className="text-[9px] text-[#8b949e]">RSI {Number(s.rsi).toFixed(1)}</div>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Perf stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {[
            { label: "Win Rate",      val: stats.win_rate + "%", color: "#00e5a0" },
            { label: "Profit Factor", val: stats.profit_factor,  color: "#0ea5e9" },
            { label: "Best Trade",    val: INR(stats.best_trade), color: "#00e5a0" },
            { label: "Total Trades",  val: stats.total_trades,    color: "#e6edf3" },
          ].map((c, i) => (
            <div key={i} className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 text-center">
              <div className="text-[10px] text-[#8b949e] uppercase tracking-wider mb-1">{c.label}</div>
              <div className="text-2xl font-bold font-mono" style={{ color: c.color }}>
                {loading ? "—" : c.val}
              </div>
            </div>
          ))}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap justify-center gap-4">
          <a
            href="http://localhost:5000"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 bg-[#00e5a0] text-[#0d1117] font-bold px-8 py-3 rounded-xl hover:opacity-90 transition-opacity text-sm"
          >
            🚀 Open Full Dashboard
          </a>
          <button
            onClick={toggleBot}
            className="inline-flex items-center gap-2 border border-[#30363d] text-[#e6edf3] font-semibold px-8 py-3 rounded-xl hover:bg-[#161b22] transition-colors text-sm"
          >
            {portfolio.bot_running ? "⏸ Pause Bot" : "▶ Resume Bot"}
          </button>
          <button
            onClick={handleKill}
            disabled={killing}
            className="inline-flex items-center gap-2 bg-[#f85149]/10 border border-[#f85149]/30 text-[#f85149] font-semibold px-8 py-3 rounded-xl hover:bg-[#f85149]/20 transition-colors text-sm"
          >
            {killing ? "Closing..." : "🛑 Kill All Positions"}
          </button>
        </div>

      </div>
    </section>
  );
}
