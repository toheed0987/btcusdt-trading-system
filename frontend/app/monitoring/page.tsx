"use client";
import { useEffect, useState } from "react";
import {
  ResponsiveContainer, ScatterChart, Scatter, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, ComposedChart, LineChart,
} from "recharts";
import { getMonitoringCurrent, getMonitoringHistory, MonitoringData } from "../lib/api";
import MetricCard from "../components/MetricCard";

export default function MonitoringPage() {
  const [current, setCurrent] = useState<MonitoringData | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    getMonitoringCurrent().then(setCurrent).catch(console.error);
    getMonitoringHistory(30).then(setHistory).catch(console.error);
  }, []);

  const pct = (v: number | null) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`);
  const num = (v: number | null) => (v === null || v === undefined ? "—" : v.toFixed(2));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Model Monitoring</h1>
        <p className="text-sm text-gray-500 mt-1">
          Active model: <span className="text-accent">{current?.model_version ?? "none trained yet"}</span>
          {current?.snapshot_date && ` · snapshot ${current.snapshot_date}`}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard label="Daily Accuracy" value={pct(current?.daily_accuracy ?? null)} />
        <MetricCard label="Weekly Accuracy" value={pct(current?.weekly_accuracy ?? null)} />
        <MetricCard label="Win Rate" value={pct(current?.win_rate ?? null)} />
        <MetricCard label="Sharpe Ratio" value={num(current?.sharpe_ratio ?? null)} />
        <MetricCard label="Profit Factor" value={num(current?.profit_factor ?? null)} />
        <MetricCard label="Max Drawdown" value={pct(current?.max_drawdown ?? null)} colorClass="text-sell" />
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Accuracy &amp; Win Rate Trend (30d)</h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={history}>
            <CartesianGrid stroke="#232838" strokeDasharray="3 3" />
            <XAxis dataKey="date" stroke="#8b93a7" fontSize={11} />
            <YAxis stroke="#8b93a7" fontSize={11} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <Tooltip contentStyle={{ background: "#131722", border: "1px solid #232838", borderRadius: 8 }}
              formatter={(v: number) => `${(v * 100).toFixed(2)}%`} />
            <Line type="monotone" dataKey="daily_accuracy" name="Daily accuracy" stroke="#4f8cff" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="weekly_accuracy" name="Weekly accuracy" stroke="#f2b705" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="win_rate" name="Win rate" stroke="#16c784" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-2">Calibration Curve</h2>
        <p className="text-xs text-gray-500 mb-4">
          Predicted probability vs. observed outcome frequency. Points on the diagonal indicate
          well-calibrated probabilities — the model neither over- nor under-states its confidence.
        </p>
        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart>
            <CartesianGrid stroke="#232838" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="predicted" name="Predicted probability" domain={[0, 1]}
              stroke="#8b93a7" fontSize={11} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <YAxis type="number" dataKey="observed" name="Observed frequency" domain={[0, 1]}
              stroke="#8b93a7" fontSize={11} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ background: "#131722", border: "1px solid #232838", borderRadius: 8 }}
              formatter={(v: number, name: string) => [`${(v * 100).toFixed(1)}%`, name]} />
            <Scatter data={current?.calibration_curve ?? []} fill="#4f8cff" />
            <Scatter data={[{ predicted: 0, observed: 0 }, { predicted: 1, observed: 1 }]}
              line={{ stroke: "#8b93a7", strokeDasharray: "4 4" }} shape={() => <g />} />
          </ScatterChart>
        </ResponsiveContainer>
        {(!current?.calibration_curve || current.calibration_curve.length === 0) && (
          <p className="text-sm text-gray-500 text-center mt-2">
            No calibration data yet — accumulates once the model has been live for at least one day.
          </p>
        )}
      </div>
    </div>
  );
}
