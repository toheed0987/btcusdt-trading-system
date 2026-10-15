"use client";
import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  getRetrainJobs, getModels, getChampion, triggerRetrain, activateModel,
  RetrainJob, ModelVersion,
} from "../lib/api";

const STATUS_COLOR: Record<string, string> = {
  success: "text-buy", failed: "text-sell", running: "text-hold", pending: "text-gray-400",
};

export default function RetrainingPage() {
  const [jobs, setJobs] = useState<RetrainJob[]>([]);
  const [models, setModels] = useState<ModelVersion[]>([]);
  const [champion, setChampion] = useState<ModelVersion | null>(null);
  const [triggering, setTriggering] = useState(false);

  const refresh = async () => {
    const [j, m, c] = await Promise.all([getRetrainJobs(), getModels(), getChampion()]);
    setJobs(j);
    setModels(m);
    setChampion(c);
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRetrain = async () => {
    setTriggering(true);
    try {
      await triggerRetrain("manual_ui_trigger");
      await refresh();
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Retraining System</h1>
          <p className="text-sm text-gray-500 mt-1">
            Daily ingestion runs at 00:15 UTC · automatic weekly retrain (Mondays 03:00 UTC by default)
          </p>
        </div>
        <button
          onClick={handleRetrain}
          disabled={triggering}
          className="bg-accent hover:bg-accent/80 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {triggering ? "Starting retrain…" : "⟳ Retrain Now"}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="metric-label">Champion Model</div>
          <div className="metric-value text-accent text-lg">{champion?.version ?? "none yet"}</div>
          {champion?.metrics && (
            <div className="text-xs text-gray-500 mt-2 space-y-1">
              <div>Validation accuracy: {(champion.metrics.val_accuracy * 100).toFixed(1)}%</div>
              <div>Brier score: {champion.metrics.val_brier_score?.toFixed(4)}</div>
            </div>
          )}
        </div>
        <div className="card">
          <div className="metric-label">Pipeline Stages</div>
          <ol className="text-sm text-gray-300 mt-2 space-y-1 list-decimal list-inside">
            <li>Daily new-data ingestion (Binance public REST/WS)</li>
            <li>Automatic feature generation (20+ technical indicators)</li>
            <li>Weekly scheduled retrain, or manual trigger</li>
            <li>Champion vs. challenger evaluation</li>
            <li>Best-model promotion + versioning</li>
          </ol>
        </div>
        <div className="card">
          <div className="metric-label">Model Versions Tracked</div>
          <div className="metric-value">{models.length}</div>
          <div className="text-xs text-gray-500 mt-1">All prior versions are retained for rollback.</div>
        </div>
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Model Versions</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-border">
              <th className="py-2">Version</th><th>Trained</th><th>Rows</th>
              <th>Val. Accuracy</th><th>Brier</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.id} className="border-b border-border/50">
                <td className="py-2 font-mono text-xs">{m.version}</td>
                <td className="text-gray-400">{new Date(m.trained_at).toLocaleString()}</td>
                <td>{m.training_rows ?? "—"}</td>
                <td>{m.metrics?.val_accuracy ? `${(m.metrics.val_accuracy * 100).toFixed(1)}%` : "—"}</td>
                <td>{m.metrics?.val_brier_score?.toFixed(4) ?? "—"}</td>
                <td>
                  {m.is_champion && <span className="text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent mr-1">champion</span>}
                  {m.is_active && <span className="text-xs px-2 py-0.5 rounded-full bg-buy/20 text-buy">active</span>}
                </td>
                <td>
                  {!m.is_active && (
                    <button
                      onClick={() => activateModel(m.id).then(refresh)}
                      className="text-xs text-accent hover:underline"
                    >
                      Activate
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {models.length === 0 && (
              <tr><td colSpan={7} className="text-center text-gray-500 py-6">No models trained yet — click "Retrain Now".</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="font-medium text-gray-300 mb-4">Job History</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-border">
              <th className="py-2">Type</th><th>Status</th><th>Triggered by</th>
              <th>Started</th><th>Finished</th><th>Result</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-b border-border/50">
                <td className="py-2">{j.job_type}</td>
                <td className={clsx("font-medium", STATUS_COLOR[j.status])}>{j.status}</td>
                <td className="text-gray-400">{j.triggered_by}</td>
                <td className="text-gray-400">{j.started_at ? new Date(j.started_at).toLocaleString() : "—"}</td>
                <td className="text-gray-400">{j.finished_at ? new Date(j.finished_at).toLocaleString() : "—"}</td>
                <td className="text-xs text-gray-500 max-w-xs truncate">
                  {j.error_message || (j.result ? JSON.stringify(j.result) : "—")}
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr><td colSpan={6} className="text-center text-gray-500 py-6">No jobs yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
