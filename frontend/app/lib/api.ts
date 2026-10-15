import axios from "axios";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export const api = axios.create({ baseURL: API_URL, timeout: 20000 });

// ---------- Types ----------
export interface Candle {
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SignalData {
  id: string;
  generated_at: string;
  action: "BUY" | "SELL" | "HOLD";
  prob_up: number;
  prob_down: number;
  confidence: number;
  price_at_signal: number;
  explanation?: Record<string, number>;
  disclaimer: string;
}

export interface Position {
  id: string;
  side: string;
  status: string;
  entry_price: number;
  exit_price?: number;
  quantity: number;
  stop_loss?: number;
  take_profit?: number;
  opened_at: string;
  closed_at?: string;
  pnl?: number;
  pnl_pct?: number;
}

export interface DashboardSummary {
  symbol: string;
  latest_price: number;
  latest_signal: SignalData | null;
  open_positions: Position[];
  realized_pnl_today: number;
  unrealized_pnl: number;
  trading_enabled: boolean;
}

export interface MonitoringData {
  model_version: string | null;
  daily_accuracy: number | null;
  weekly_accuracy: number | null;
  win_rate: number | null;
  sharpe_ratio: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  calibration_curve: { bucket_mid: number; predicted: number; observed: number; n: number }[];
  snapshot_date: string | null;
}

export interface ModelVersion {
  id: string;
  version: string;
  algorithm: string;
  trained_at: string;
  training_rows?: number;
  is_active: boolean;
  is_champion: boolean;
  metrics?: Record<string, any>;
}

export interface RetrainJob {
  id: string;
  job_type: string;
  status: string;
  triggered_by: string;
  started_at?: string;
  finished_at?: string;
  result?: Record<string, any>;
  error_message?: string;
}

export interface AdminSettings {
  trading_enabled: boolean;
  buy_prob_threshold: number;
  sell_prob_threshold: number;
  min_confidence: number;
  max_position_size_pct: number;
  max_open_positions: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  daily_loss_limit_pct: number;
  updated_at: string;
  updated_by?: string;
}

// ---------- Dashboard ----------
export const getCandles = (limit = 200) =>
  api.get<Candle[]>("/api/dashboard/candles", { params: { limit } }).then((r) => r.data);

export const getSummary = () =>
  api.get<DashboardSummary>("/api/dashboard/summary").then((r) => r.data);

// ---------- Monitoring ----------
export const getMonitoringCurrent = () =>
  api.get<MonitoringData>("/api/monitoring/current").then((r) => r.data);

export const getMonitoringHistory = (days = 30) =>
  api.get("/api/monitoring/history", { params: { days } }).then((r) => r.data);

// ---------- Retraining ----------
export const getRetrainJobs = () =>
  api.get<RetrainJob[]>("/api/retraining/jobs").then((r) => r.data);

export const getModels = () =>
  api.get<ModelVersion[]>("/api/retraining/models").then((r) => r.data);

export const getChampion = () =>
  api.get<ModelVersion | null>("/api/retraining/models/champion").then((r) => r.data);

export const triggerRetrain = (reason = "manual_trigger") =>
  api.post<RetrainJob>("/api/retraining/retrain", { reason }).then((r) => r.data);

export const activateModel = (modelId: string) =>
  api.post<ModelVersion>(`/api/retraining/models/${modelId}/activate`).then((r) => r.data);

// ---------- Backtest ----------
export const runBacktest = (payload: Record<string, any>) =>
  api.post("/api/backtest/run", payload).then((r) => r.data);

export const listBacktests = () => api.get("/api/backtest").then((r) => r.data);

// ---------- Admin ----------
export const getAdminSettings = () =>
  api.get<AdminSettings>("/api/admin/settings").then((r) => r.data);

export const updateAdminSettings = (payload: Partial<AdminSettings>) =>
  api.put<AdminSettings>("/api/admin/settings", payload).then((r) => r.data);

export const getAuditLog = () => api.get("/api/admin/audit-log").then((r) => r.data);
