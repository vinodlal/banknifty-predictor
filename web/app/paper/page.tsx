"use client";

import { useEffect, useState } from "react";
import { getScoreboard, getTrades, type Scoreboard } from "@/lib/api";

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-black/5 dark:bg-white/10 rounded-lg px-3 py-2">
      <div className="text-xs text-black/50 dark:text-white/50">{label}</div>
      <div className="text-lg font-medium">{value}</div>
    </div>
  );
}

function fmtPct(v: number | null) {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}
function fmtR(v: number | null | undefined) {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}R`;
}

export default function PaperPage() {
  const [overall, setOverall] = useState<Scoreboard | null>(null);
  const [byStrategy, setByStrategy] = useState<Record<string, Scoreboard>>({});
  const [openTrades, setOpenTrades] = useState<Record<string, unknown>[]>([]);
  const [closedTrades, setClosedTrades] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    getScoreboard().then((s) => setOverall(s as Scoreboard));
    getScoreboard("strategy").then((s) => setByStrategy(s as Record<string, Scoreboard>));
    getTrades("open").then((r) => setOpenTrades(r.trades));
    getTrades("closed").then((r) => setClosedTrades(r.trades));
  }, []);

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-xl font-medium">Paper-trading scoreboard</h1>

      {overall && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          <StatTile label="Trades" value={String(overall.trades)} />
          <StatTile label="Win rate" value={fmtPct(overall.win_rate)} />
          <StatTile label="Expectancy" value={fmtR(overall.expectancy_r)} />
          <StatTile label="Profit factor" value={overall.profit_factor?.toFixed(2) ?? "—"} />
          <StatTile label="Max drawdown" value={fmtR(overall.max_drawdown_r)} />
        </div>
      )}

      {Object.keys(byStrategy).length > 0 && (
        <div>
          <h2 className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50 mb-2">By strategy</h2>
          <div className="space-y-1">
            {Object.entries(byStrategy).map(([name, sb]) => (
              <div key={name} className="flex items-center justify-between text-sm border border-black/10 dark:border-white/10 rounded-lg px-3 py-2">
                <span className="font-medium">{name}</span>
                <span>
                  {sb.trades} trades · {fmtPct(sb.win_rate)} win rate · {fmtR(sb.avg_r)} avg
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50 mb-2">
          Open trades ({openTrades.length})
        </h2>
        {openTrades.length === 0 ? (
          <p className="text-sm text-black/40 dark:text-white/40">None open.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-black/50 dark:text-white/50 text-left">
                <tr>
                  <th className="py-1 pr-4">Symbol</th><th className="py-1 pr-4">Bias</th>
                  <th className="py-1 pr-4">Entry</th><th className="py-1 pr-4">Stop</th><th className="py-1 pr-4">Target</th>
                </tr>
              </thead>
              <tbody>
                {openTrades.map((t) => (
                  <tr key={String(t.id)} className="border-t border-black/10 dark:border-white/10">
                    <td className="py-1 pr-4 font-medium">{String(t.symbol)}</td>
                    <td className="py-1 pr-4">{String(t.bias)}</td>
                    <td className="py-1 pr-4">{String(t.entry)}</td>
                    <td className="py-1 pr-4">{String(t.stop)}</td>
                    <td className="py-1 pr-4">{String(t.target1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h2 className="text-xs uppercase tracking-wide text-black/50 dark:text-white/50 mb-2">
          Closed trades ({closedTrades.length})
        </h2>
        {closedTrades.length === 0 ? (
          <p className="text-sm text-black/40 dark:text-white/40">None yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-black/50 dark:text-white/50 text-left">
                <tr>
                  <th className="py-1 pr-4">Symbol</th><th className="py-1 pr-4">Bias</th>
                  <th className="py-1 pr-4">Reason</th><th className="py-1 pr-4">Result</th>
                </tr>
              </thead>
              <tbody>
                {closedTrades.map((t) => (
                  <tr key={String(t.id)} className="border-t border-black/10 dark:border-white/10">
                    <td className="py-1 pr-4 font-medium">{String(t.symbol)}</td>
                    <td className="py-1 pr-4">{String(t.bias)}</td>
                    <td className="py-1 pr-4">{String(t.close_reason)}</td>
                    <td className={`py-1 pr-4 ${Number(t.r_multiple) >= 0 ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"}`}>
                      {fmtR(t.r_multiple as number)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
