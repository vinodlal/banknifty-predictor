"use client";

import { useEffect, useState } from "react";
import { getStock, getHoldings, searchStocks, type Signal, ApiError } from "@/lib/api";
import SignalCard from "@/components/SignalCard";

export default function StockPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Array<{ tradingsymbol: string; name: string }>>([]);
  const [holdings, setHoldings] = useState<Array<{ tradingsymbol: string; quantity: number }>>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getHoldings()
      .then((r) => setHoldings(r.holdings))
      .catch(() => setHoldings([]));
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) return; // dropdown visibility is gated on query length below,
    const t = setTimeout(() => {          // so stale results here never render while query is short
      searchStocks(query)
        .then((r) => setResults(r.results))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  function loadSymbol(symbol: string) {
    setSelected(symbol);
    setSignal(null);
    setError(null);
    setLoading(true);
    getStock(symbol)
      .then(setSignal)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load."))
      .finally(() => setLoading(false));
  }

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-xl font-medium">Stock desk</h1>

      <div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search any NSE stock (e.g. TCS, HDFCBANK)…"
          className="w-full border border-black/15 dark:border-white/15 rounded-lg px-3 py-2 text-sm bg-transparent"
        />
        {query.trim().length >= 2 && results.length > 0 && (
          <div className="mt-1 border border-black/10 dark:border-white/10 rounded-lg divide-y divide-black/10 dark:divide-white/10">
            {results.map((r) => (
              <button
                key={r.tradingsymbol}
                onClick={() => {
                  loadSymbol(r.tradingsymbol);
                  setQuery("");
                  setResults([]);
                }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10"
              >
                <span className="font-medium">{r.tradingsymbol}</span>{" "}
                <span className="text-black/50 dark:text-white/50">{r.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {holdings.length > 0 && (
        <div>
          <h2 className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50 mb-2">Your holdings</h2>
          <div className="flex flex-wrap gap-2">
            {holdings.map((h) => (
              <button
                key={h.tradingsymbol}
                onClick={() => loadSymbol(h.tradingsymbol)}
                className={`text-sm px-3 py-1.5 rounded-full border ${
                  selected === h.tradingsymbol
                    ? "bg-black/10 dark:bg-white/15 border-black/20 dark:border-white/20"
                    : "border-black/15 dark:border-white/15 hover:bg-black/5 dark:hover:bg-white/10"
                }`}
              >
                {h.tradingsymbol}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && <p className="text-sm text-black/50">Computing live signal for {selected}…</p>}
      {error && <p className="text-sm text-red-700 dark:text-red-400">{error}</p>}
      {signal && (
        <SignalCard
          sig={signal}
          extra={
            signal.strategies && (
              <div className="mt-3 space-y-2">
                {signal.strategies.holding && (
                  <div className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm">
                    <div className="text-xs text-black/50 dark:text-white/50 mb-1">If you hold</div>
                    {signal.strategies.holding}
                  </div>
                )}
                {signal.strategies.btst && (
                  <div className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm">
                    <div className="text-xs text-black/50 dark:text-white/50 mb-1">BTST</div>
                    <span className="font-medium">{signal.strategies.btst.verdict}</span> — {signal.strategies.btst.reason}
                  </div>
                )}
              </div>
            )
          }
        />
      )}
    </main>
  );
}
