"use client";
import { useEffect, useState } from "react";
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { getCandles, getSummary, Candle, DashboardSummary } from "./lib/api";
import { useLiveSocket } from "./lib/useLiveSocket";
import MetricCard from "./components/MetricCard";
import clsx from "clsx";

const ACTION_COLOR: Record<string, string> = {
  BUY: "text-buy", SELL: "text-sell", HOLD: "text-hold",
};
const ACTION_BG: Record<string, string> = {
  BUY: "bg-buy/15 border-buy/40", SELL: "bg-sell/15 border-sell/40", HOLD: "bg-hold/15 border-hold/40",
};

export default function DashboardPage() {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const { lastPrice, lastSignal, connected } = useLiveSocket();

  useEffect(() => {
    const load = async () => {
      try {
        const [c, s] = await Promise.all([getCandles(240), getSummary()]);
        setCandles(c);
        setSummary(s);
      } catch (e) {
        console.error("Failed to load dashboard data", e);
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const chartData = candles.map((c) => ({
    time: new Date(c.open_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    close: c.close,
  }));

  const livePrice = lastPrice?.price ?? summary?.latest_price;
  const signal = lastSignal ?? summary?.latest_signal;
  const action = signal?.action ?? "HOLD";
  const probUp = signal?.prob_up ?? 0.5;
  const probDown = signal?.prob_down ?? 0.5;
  const confidence = signal?.confidence ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <span className={clsx("text-xs px-2 py-1 rounded-full border",
          connected ? "border-buy/40 text-buy" : "border-sell/40 text-sell")}>
          {connected ? "● live" : "○ reconnecting…"}
        </span>
      </div>

      {/* Live chart */}
      <div className="card">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="font-medium text-gray-300">BTC/USDT — Live Price</h2>
          <span className="text-2xl font-semibold">
            {livePrice ? `$${livePrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "—"}
          </span>
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartData}>
            <CartesianGrid stroke="#232838" strokeDasharray="3 3" />
            <XAxis dataKey="time" stroke="#8b93a7" fontSize={11} minTickGap={40} />
            <YAxis stroke="#8b93a7" fontSize={11} domain={["auto", "auto"]}
              tickFormatter={(v) => `$${Number(v).toLocaleString()}`} width={90} />
            <Tooltip
              contentStyle={{ background: "#131722", border: "1px solid #232838", borderRadius: 8 }}
              formatter={(v: number) => [`$${v.toLocaleString()}`, "Close"]}
            />
            <Line type="monotone" dataKey="close" stroke="#4f8cff" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Signal panel */}
      <div className={clsx("card border-2", ACTION_BG[action])}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="metric-label">Current Signal</div>
            <div className={clsx("text-4xl font-bold mt-1", ACTION_COLOR[action])}>{action}</div>
          </div>
          <div className="grid grid-cols-3 gap-6">
            <div>
              <div className="metric-label">Probability Up</div>
              <div className="metric-value text-buy">{(probUp * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="metric-label">Probability Down</div>
              <div className="metric-value text-sell">{(probDown * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="metric-label">Confidence</div>
              <div className="metric-value">{(confidence * 100).toFixed(1)}%</div>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-4 italic">
          {signal?.disclaimer ??
            "Probabilistic estimate only. Not a guarantee of future price movement."}
        </p>
        {signal?.explanation && Object.keys(signal.explanation).length > 0 && (
          <div className="mt-4 border-t border-white/10 pt-3">
            <div className="metric-label mb-2">Why this signal — top contributing features (SHAP)</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(signal.explanation).map(([feature, impact]: [string, any]) => (
                <span key={feature}
                  className={clsx("text-xs px-2 py-1 rounded-md border",
                    impact > 0 ? "border-buy/40 text-buy" : "border-sell/40 text-sell")}>
                  {feature}: {impact > 0 ? "+" : ""}{Number(impact).toFixed(4)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* PnL + open positions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard label="Realized PnL (today)" value={`$${(summary?.realized_pnl_today ?? 0).toFixed(2)}`}
          colorClass={(summary?.realized_pnl_today ?? 0) >= 0 ? "text-buy" : "text-sell"} />
        <MetricCard label="Unrealized PnL" value={`$${(summary?.unrealized_pnl ?? 0).toFixed(2)}`}
          colorClass={(summary?.unrealized_pnl ?? 0) >= 0 ? "text-buy" : "text-sell"} />
        <MetricCard label="Trading Status" value={summary?.trading_enabled ? "Enabled" : "Disabled"}
          colorClass={summary?.trading_enabled ? "text-buy" : "text-gray-400"}
          sub="Configure in Admin Panel" />
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Open Positions</h2>
        {(!summary?.open_positions || summary.open_positions.length === 0) ? (
          <p className="text-sm text-gray-500">No open positions.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-border">
                <th className="py-2">Side</th><th>Entry</th><th>Qty</th>
                <th>Stop Loss</th><th>Take Profit</th><th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {summary.open_positions.map((p) => (
                <tr key={p.id} className="border-b border-border/50">
                  <td className={clsx("py-2 font-medium", p.side === "LONG" ? "text-buy" : "text-sell")}>
                    {p.side}
                  </td>
                  <td>${Number(p.entry_price).toLocaleString()}</td>
                  <td>{Number(p.quantity).toFixed(6)}</td>
                  <td>{p.stop_loss ? `$${Number(p.stop_loss).toLocaleString()}` : "—"}</td>
                  <td>{p.take_profit ? `$${Number(p.take_profit).toLocaleString()}` : "—"}</td>
                  <td className="text-gray-400">{new Date(p.opened_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
