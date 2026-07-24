"use client";

import { useEffect, useState } from "react";
import { getBrief, type Brief, ApiError } from "@/lib/api";

const SENTIMENT_STYLE: Record<string, string> = {
  bullish: "text-green-700 dark:text-green-400",
  bearish: "text-red-700 dark:text-red-400",
  neutral: "text-black/50 dark:text-white/50",
};

export default function BriefPage() {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBrief()
      .then(setBrief)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load the brief."));
  }, []);

  if (error) {
    return (
      <main className="max-w-4xl mx-auto p-6">
        <p className="text-sm text-black/60 dark:text-white/60">
          {error} Run <code className="bg-black/5 dark:bg-white/10 px-1 rounded">python -m core.brief.run</code> to
          generate one.
        </p>
      </main>
    );
  }
  if (!brief) {
    return <main className="max-w-4xl mx-auto p-6 text-sm text-black/50">Loading brief…</main>;
  }

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-xl font-medium">Pre-open morning brief</h1>
        <p className="text-xs text-black/50 dark:text-white/50">{brief.generated_at}</p>
      </div>

      <p className="text-sm leading-relaxed border-l-2 border-black/10 dark:border-white/15 pl-3">{brief.status}</p>

      <div>
        <h2 className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50 mb-2">Snapshot</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {Object.entries(brief.snapshot).map(([name, tile]) => (
            <div key={name} className="border border-black/10 dark:border-white/10 rounded-lg p-3">
              <div className="text-xs text-black/50 dark:text-white/50">{name}</div>
              {tile.last_price == null ? (
                <div className="text-sm text-black/40 dark:text-white/40 mt-1">unavailable</div>
              ) : (
                <>
                  <div className="text-base font-medium">{tile.last_price.toLocaleString()}</div>
                  {tile.change_pct != null && (
                    <div className={tile.change_pct >= 0 ? "text-green-700 dark:text-green-400 text-xs" : "text-red-700 dark:text-red-400 text-xs"}>
                      {tile.change_pct >= 0 ? "▲" : "▼"} {tile.change_pct.toFixed(2)}%
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          {brief.pcr != null && (
            <div className="border border-black/10 dark:border-white/10 rounded-lg p-3">
              <div className="text-xs text-black/50 dark:text-white/50">PCR</div>
              <div className="text-base font-medium">{brief.pcr}</div>
            </div>
          )}
        </div>
      </div>

      {brief.top_signals.length > 0 && (
        <div>
          <h2 className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50 mb-2">Top signals</h2>
          <div className="space-y-1">
            {brief.top_signals.map((s) => (
              <div key={s.symbol} className="flex items-center justify-between text-sm border border-black/10 dark:border-white/10 rounded-lg px-3 py-2">
                <span className="font-medium">{s.symbol}</span>
                <span>
                  {s.bias} · score {s.score} · {s.confidence} confidence
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-4">
        {(["india", "global"] as const).map((bucket) => (
          <div key={bucket}>
            <h2 className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50 mb-2 capitalize">
              {bucket} news
            </h2>
            <ul className="space-y-1.5 text-sm">
              {brief.news[bucket].slice(0, 6).map((n, i) => (
                <li key={i} className={SENTIMENT_STYLE[n.sentiment]}>
                  {n.title}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <p className="text-[11px] text-black/40 dark:text-white/40">{brief.disclaimer}</p>
    </main>
  );
}
