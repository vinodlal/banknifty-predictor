const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json();
}

export interface Snapshot {
  [name: string]: { last_price: number | null; prev_close: number | null; change_pct: number | null; source: string | null };
}

export interface NewsItem {
  title: string;
  link: string;
  source: string;
  published: string | null;
  sentiment: "bullish" | "bearish" | "neutral";
}

export interface Brief {
  generated_at: string;
  snapshot: Snapshot;
  pcr: number | null;
  status: string;
  news: { india: NewsItem[]; global: NewsItem[] };
  top_signals: Signal[];
  disclaimer: string;
}

export interface TradePlan {
  bias: string;
  entry: number;
  stop: number;
  target1: number;
  target2: number;
  risk_reward: number | null;
  size: number;
}

export interface Signal {
  symbol: string;
  kind: string;
  horizon: string;
  date: string;
  price: number;
  score: number;
  bias: "Long" | "Short" | "Neutral";
  confidence: "high" | "medium" | "low";
  component_scores: Record<string, number>;
  reasons: string[];
  levels: { pivot: number; support: number; resistance: number; r1: number; s1: number; atm_strike: number | null };
  pcr: number | null;
  ma: { price: number; values: Record<string, number | null>; above: number[]; below: number[]; trend: string };
  structure: string;
  regime: string;
  adx: number | null;
  relationships: Array<{ name: string; change_pct: number; corr_20d: number | null; relationship: string; implication: string }>;
  disclaimer: string;
  oi?: { buildup: string; implication: string; oi: number | null; oi_chg_pct: number };
  basis?: { pct: number; reading: string; future_price: number; spot_price: number };
  trade_plan?: TradePlan | null;
  is_holding?: boolean;
  has_futures?: boolean;
  strategies?: {
    holding?: string;
    futures?: TradePlan | null;
    btst?: { verdict: string; reason: string };
  };
}

export interface Scoreboard {
  trades: number;
  win_rate: number | null;
  avg_r: number | null;
  expectancy_r: number | null;
  profit_factor: number | null;
  max_drawdown_r: number;
  equity_curve_r: number[];
}

export const getBrief = () => apiFetch<Brief>("/brief");
export const getFutures = (name: string) => apiFetch<Signal>(`/futures/${name}`);
export const getStock = (symbol: string) => apiFetch<Signal>(`/stock/${symbol}`);
export const searchStocks = (q: string) =>
  apiFetch<{ query: string; results: Array<{ tradingsymbol: string; name: string }> }>(
    `/stock/search?q=${encodeURIComponent(q)}`
  );
export const getHoldings = () => apiFetch<{ holdings: Array<{ tradingsymbol: string; quantity: number; average_price: number; last_price: number }> }>("/stock/holdings");
export const getScoreboard = (by?: string) => apiFetch<Scoreboard | Record<string, Scoreboard>>(`/paper/scoreboard${by ? `?by=${by}` : ""}`);
export const getTrades = (status: "open" | "closed") => apiFetch<{ status: string; trades: Record<string, unknown>[] }>(`/paper/trades?status=${status}`);
