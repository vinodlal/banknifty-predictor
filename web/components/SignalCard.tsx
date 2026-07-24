import type { Signal } from "@/lib/api";

const BIAS_STYLE: Record<string, string> = {
  Long: "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/40 dark:text-green-300 dark:border-green-700",
  Short: "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/40 dark:text-red-300 dark:border-red-700",
  Neutral: "bg-gray-100 text-gray-700 border-gray-300 dark:bg-gray-800/60 dark:text-gray-300 dark:border-gray-600",
};

function Tile({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="bg-black/5 dark:bg-white/10 rounded-lg px-3 py-2">
      <div className="text-xs text-black/50 dark:text-white/50">{label}</div>
      <div className="text-base font-medium">{value ?? "—"}</div>
    </div>
  );
}

export default function SignalCard({ sig, extra }: { sig: Signal; extra?: React.ReactNode }) {
  return (
    <div className="border border-black/10 dark:border-white/10 rounded-xl p-4 bg-white dark:bg-white/[0.03]">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-medium tracking-tight">{sig.symbol}</span>
            <span className="text-xs px-2 py-0.5 rounded bg-black/5 dark:bg-white/10 text-black/60 dark:text-white/60">
              {sig.kind} · {sig.horizon}
            </span>
          </div>
          <div className="text-xs text-black/50 dark:text-white/50 mt-0.5">{sig.date}</div>
        </div>
        <div className="text-right">
          <span className={`inline-block text-sm font-medium px-3 py-1 rounded-md border ${BIAS_STYLE[sig.bias]}`}>
            {sig.bias}
          </span>
          <div className="text-xs text-black/50 dark:text-white/50 mt-1">
            {sig.confidence} confidence · score {sig.score}/100
          </div>
        </div>
      </div>

      <div className="mt-3 relative h-2 rounded bg-gradient-to-r from-red-300 via-gray-200 to-green-300 dark:from-red-800 dark:via-gray-700 dark:to-green-800">
        <div
          className="absolute top-[-3px] w-[3px] h-3.5 rounded bg-black dark:bg-white"
          style={{ left: `${sig.score}%` }}
        />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4">
        <Tile label="Price" value={sig.price.toLocaleString()} />
        <Tile label="Support" value={sig.levels.support.toLocaleString()} />
        <Tile label="Pivot" value={sig.levels.pivot.toLocaleString()} />
        <Tile label="Resistance" value={sig.levels.resistance.toLocaleString()} />
      </div>

      {sig.trade_plan && (
        <div className="mt-3 border border-black/10 dark:border-white/10 rounded-lg p-3">
          <div className="text-xs text-black/50 dark:text-white/50 mb-2">Trade plan</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
            <div>Entry <span className="font-medium">{sig.trade_plan.entry.toLocaleString()}</span></div>
            <div>Stop <span className="font-medium">{sig.trade_plan.stop.toLocaleString()}</span></div>
            <div>Target <span className="font-medium">{sig.trade_plan.target1.toLocaleString()}</span></div>
            <div>R:R <span className="font-medium">{sig.trade_plan.risk_reward ?? "—"}</span></div>
            <div>Size <span className="font-medium">{sig.trade_plan.size}</span></div>
          </div>
        </div>
      )}

      {sig.oi && (
        <div className="mt-2 text-sm text-black/70 dark:text-white/70">
          OI: <span className="font-medium">{sig.oi.buildup.replace("_", " ")}</span> ({sig.oi.implication})
          {sig.basis && <> · Basis {sig.basis.pct >= 0 ? "+" : ""}{sig.basis.pct}% ({sig.basis.reading})</>}
        </div>
      )}

      <div className="mt-3">
        <div className="text-xs text-black/50 dark:text-white/50 mb-1">Why this call</div>
        <ul className="text-sm space-y-1">
          {sig.reasons.map((r, i) => (
            <li key={i} className="text-black/80 dark:text-white/80">
              · {r}
            </li>
          ))}
        </ul>
      </div>

      {extra}

      <div className="mt-3 text-[11px] text-black/40 dark:text-white/40">{sig.disclaimer}</div>
    </div>
  );
}
