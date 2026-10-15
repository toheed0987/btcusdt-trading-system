"use client";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { getAdminSettings, updateAdminSettings, getAuditLog, AdminSettings } from "../lib/api";

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm text-gray-300">{label}</span>
      {children}
      {hint && <span className="text-xs text-gray-500">{hint}</span>}
    </label>
  );
}

export default function AdminPage() {
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [form, setForm] = useState<Partial<AdminSettings>>({});
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [auditLog, setAuditLog] = useState<any[]>([]);

  const refresh = async () => {
    const s = await getAdminSettings();
    setSettings(s);
    setForm(s);
    const log = await getAuditLog();
    setAuditLog(log);
  };

  useEffect(() => { refresh(); }, []);

  const update = (field: keyof AdminSettings, value: any) => setForm((f) => ({ ...f, [field]: value }));

  const save = async () => {
    setSaving(true);
    setSavedMsg(null);
    try {
      const updated = await updateAdminSettings({ ...form, updated_by: "admin_ui" });
      setSettings(updated);
      setSavedMsg("Settings saved.");
      await refresh();
    } catch (e) {
      setSavedMsg("Failed to save settings.");
    } finally {
      setSaving(false);
      setTimeout(() => setSavedMsg(null), 3000);
    }
  };

  if (!settings) return <p className="text-gray-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Admin Panel</h1>

      <div className={clsx("card border-2", form.trading_enabled ? "border-buy/40" : "border-border")}>
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Trading Enabled</div>
            <div className="text-xs text-gray-500 mt-1">
              When disabled, the system generates signals and monitors performance but never opens
              new positions.
            </div>
          </div>
          <button
            onClick={() => update("trading_enabled", !form.trading_enabled)}
            className={clsx(
              "relative w-14 h-7 rounded-full transition-colors",
              form.trading_enabled ? "bg-buy" : "bg-gray-600"
            )}
          >
            <span className={clsx(
              "absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full transition-transform",
              form.trading_enabled && "translate-x-7"
            )} />
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Probability Thresholds</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Field label="Buy probability threshold" hint="Min. prob-up required to trigger BUY">
            <input type="number" min={0.5} max={0.99} step={0.01}
              value={form.buy_prob_threshold ?? 0.6}
              onChange={(e) => update("buy_prob_threshold", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
          <Field label="Sell probability threshold" hint="Min. prob-down required to trigger SELL">
            <input type="number" min={0.5} max={0.99} step={0.01}
              value={form.sell_prob_threshold ?? 0.6}
              onChange={(e) => update("sell_prob_threshold", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
          <Field label="Minimum confidence" hint="Below this, the system outputs HOLD regardless of threshold">
            <input type="number" min={0} max={1} step={0.01}
              value={form.min_confidence ?? 0.2}
              onChange={(e) => update("min_confidence", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
        </div>
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Risk Settings</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Field label="Max position size (% of capital)">
            <input type="number" min={0.01} max={1} step={0.01}
              value={form.max_position_size_pct ?? 0.1}
              onChange={(e) => update("max_position_size_pct", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
          <Field label="Max open positions">
            <input type="number" min={1} max={20} step={1}
              value={form.max_open_positions ?? 1}
              onChange={(e) => update("max_open_positions", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
          <Field label="Daily loss limit (%)" hint="Trading pauses for the day if breached">
            <input type="number" min={0.01} max={1} step={0.01}
              value={form.daily_loss_limit_pct ?? 0.05}
              onChange={(e) => update("daily_loss_limit_pct", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
        </div>
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Stop-Loss / Take-Profit</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Stop loss (%)">
            <input type="number" min={0.001} max={0.5} step={0.005}
              value={form.stop_loss_pct ?? 0.02}
              onChange={(e) => update("stop_loss_pct", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
          <Field label="Take profit (%)">
            <input type="number" min={0.001} max={1} step={0.005}
              value={form.take_profit_pct ?? 0.04}
              onChange={(e) => update("take_profit_pct", Number(e.target.value))}
              className="bg-bg border border-border rounded-md px-2 py-1.5" />
          </Field>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button onClick={save} disabled={saving}
          className="bg-accent hover:bg-accent/80 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium">
          {saving ? "Saving…" : "Save Settings"}
        </button>
        {savedMsg && <span className="text-sm text-gray-400">{savedMsg}</span>}
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Recent Changes (Audit Log)</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-border">
              <th className="py-2">When</th><th>By</th><th>Field</th><th>Old</th><th>New</th>
            </tr>
          </thead>
          <tbody>
            {auditLog.map((row, i) => (
              <tr key={i} className="border-b border-border/50">
                <td className="py-2 text-gray-400">{new Date(row.changed_at).toLocaleString()}</td>
                <td>{row.changed_by}</td>
                <td className="font-mono text-xs">{row.field}</td>
                <td className="text-sell">{row.old_value}</td>
                <td className="text-buy">{row.new_value}</td>
              </tr>
            ))}
            {auditLog.length === 0 && (
              <tr><td colSpan={5} className="text-center text-gray-500 py-6">No changes yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
