"use client";
import { useState } from "react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell,
} from "recharts";
import clsx from "clsx";
import { runBacktest } from "../lib/api";
import MetricCard from "../components/MetricCard";

function defaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 14);
  return { start: start.toISOString().slice(0, 16), end: end.toISOString().slice(0, 16) };
}

export default function BacktestPage() {
  const { start, end } = defaultDates();
  const [form, setForm] = useState({
    period_start: start, period_end: end, initial_capital: 10000,
    buy_prob_threshold: 0.6, sell_prob_threshold: 0.6,
    stop_loss_pct: 0.02, take_profit_pct: 0.04, position_size_pct: 0.1,
  });
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (field: string, value: any) => setForm((f) => ({ ...f, [field]: value }));

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        ...form,
        period_start: new Date(form.period_start).toISOString(),
        period_end: new Date(form.period_end).toISOString(),
      };
      const data = await runBacktest(payload);
      setResult(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Backtest failed. Ensure a champion model has been trained.");
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics ?? {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Backtesting</h1>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Backtest Configuration</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Period start</span>
            <input type="datetime-local" value={form.period_start}
              onChange={(e) => update("period_start", e.target.value)}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Period end</span>
            <input type="datetime-local" value={form.period_end}
              onChange={(e) => update("period_end", e.target.value)}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Initial capital ($)</span>
            <input type="number" value={form.initial_capital}
              onChange={(e) => update("initial_capital", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Position size (% capital)</span>
            <input type="number" step="0.01" value={form.position_size_pct}
              onChange={(e) => update("position_size_pct", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Buy prob. threshold</span>
            <input type="number" step="0.01" value={form.buy_prob_threshold}
              onChange={(e) => update("buy_prob_threshold", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Sell prob. threshold</span>
            <input type="number" step="0.01" value={form.sell_prob_threshold}
              onChange={(e) => update("sell_prob_threshold", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Stop loss (%)</span>
            <input type="number" step="0.005" value={form.stop_loss_pct}
              onChange={(e) => update("stop_loss_pct", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-gray-500">Take profit (%)</span>
            <input type="number" step="0.005" value={form.take_profit_pct}
              onChange={(e) => update("take_profit_pct", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </label>
        </div>
        <button onClick={submit} disabled={loading}
          className="mt-4 bg-accent hover:bg-accent/80 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium">
          {loading ? "Running backtest…" : "Run Backtest"}
        </button>
        {error && <p className="text-sm text-sell mt-3">{error}</p>}
      </div>

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard label="Total Return" value={`${m.total_return_pct?.toFixed(2)}%`}
              colorClass={m.total_return_pct >= 0 ? "text-buy" : "text-sell"} />
            <MetricCard label="Sharpe Ratio" value={m.sharpe_ratio?.toFixed(2) ?? "—"} />
            <MetricCard label="Profit Factor" value={m.profit_factor?.toFixed(2) ?? "∞"} />
            <MetricCard label="Max Drawdown" value={`${m.max_drawdown_pct?.toFixed(2)}%`} colorClass="text-sell" />
            <MetricCard label="Win Rate" value={`${(m.win_rate * 100)?.toFixed(1)}%`} />
            <MetricCard label="Total Trades" value={`${m.total_trades ?? 0}`} />
            <MetricCard label="Winning Trades" value={`${m.winning_trades ?? 0}`} colorClass="text-buy" />
            <MetricCard label="Losing Trades" value={`${m.losing_trades ?? 0}`} colorClass="text-sell" />
          </div>

          <div className="card">
            <h2 className="font-medium text-gray-300 mb-4">Equity Curve</h2>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={result.equity_curve}>
                <defs>
                  <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4f8cff" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#4f8cff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#232838" strokeDasharray="3 3" />
                <XAxis dataKey="t" stroke="#8b93a7" fontSize={10} minTickGap={60}
                  tickFormatter={(v) => new Date(v).toLocaleDateString()} />
                <YAxis stroke="#8b93a7" fontSize={11} tickFormatter={(v) => `$${Number(v).toLocaleString()}`} width={90} />
                <Tooltip contentStyle={{ background: "#131722", border: "1px solid #232838", borderRadius: 8 }}
                  labelFormatter={(v) => new Date(v).toLocaleString()}
                  formatter={(v: number) => [`$${v.toLocaleString()}`, "Equity"]} />
                <Area type="monotone" dataKey="equity" stroke="#4f8cff" fill="url(#equityFill)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <h2 className="font-medium text-gray-300 mb-4">Monthly Returns</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={result.monthly_returns}>
                  <CartesianGrid stroke="#232838" strokeDasharray="3 3" />
                  <XAxis dataKey="month" stroke="#8b93a7" fontSize={11} />
                  <YAxis stroke="#8b93a7" fontSize={11} tickFormatter={(v) => `${v}%`} />
                  <Tooltip contentStyle={{ background: "#131722", border: "1px solid #232838", borderRadius: 8 }}
                    formatter={(v: number) => [`${v.toFixed(2)}%`, "Return"]} />
                  <Bar dataKey="return_pct">
                    {result.monthly_returns?.map((entry: any, i: number) => (
                      <Cell key={i} fill={entry.return_pct >= 0 ? "#16c784" : "#ea3943"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <h2 className="font-medium text-gray-300 mb-4">Drawdown</h2>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={computeDrawdownSeries(result.equity_curve)}>
                  <CartesianGrid stroke="#232838" strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke="#8b93a7" fontSize={10} minTickGap={60}
                    tickFormatter={(v) => new Date(v).toLocaleDateString()} />
                  <YAxis stroke="#8b93a7" fontSize={11} tickFormatter={(v) => `${v}%`} />
                  <Tooltip contentStyle={{ background: "#131722", border: "1px solid #232838", borderRadius: 8 }}
                    formatter={(v: number) => [`${v.toFixed(2)}%`, "Drawdown"]} />
                  <Area type="monotone" dataKey="drawdown_pct" stroke="#ea3943" fill="#ea394333" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <h2 className="font-medium text-gray-300 mb-4">Trade Log</h2>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-panel">
                  <tr className="text-left text-gray-500 border-b border-border">
                    <th className="py-2">Side</th><th>Entry</th><th>Exit</th><th>Qty</th>
                    <th>PnL</th><th>PnL %</th><th>Exit Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades?.map((t: any, i: number) => (
                    <tr key={i} className="border-b border-border/50">
                      <td className={clsx("py-2 font-medium", t.side === "LONG" ? "text-buy" : "text-sell")}>{t.side}</td>
                      <td>${Number(t.entry_price).toLocaleString()}</td>
                      <td>${Number(t.exit_price).toLocaleString()}</td>
                      <td>{Number(t.quantity).toFixed(6)}</td>
                      <td className={t.pnl >= 0 ? "text-buy" : "text-sell"}>${Number(t.pnl).toFixed(2)}</td>
                      <td className={t.pnl_pct >= 0 ? "text-buy" : "text-sell"}>{Number(t.pnl_pct).toFixed(2)}%</td>
                      <td className="text-gray-400">{t.exit_reason}</td>
                    </tr>
                  ))}
                  {(!result.trades || result.trades.length === 0) && (
                    <tr><td colSpan={7} className="text-center text-gray-500 py-6">No trades were triggered in this window.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function computeDrawdownSeries(equityCurve: { t: string; equity: number }[]) {
  let peak = -Infinity;
  return (equityCurve || []).map((p) => {
    peak = Math.max(peak, p.equity);
    const drawdown_pct = peak > 0 ? ((p.equity - peak) / peak) * 100 : 0;
    return { t: p.t, drawdown_pct };
  });
}
