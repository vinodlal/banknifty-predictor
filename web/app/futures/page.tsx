"use client";

import { useEffect, useState } from "react";
import { getFutures, type Signal, ApiError } from "@/lib/api";
import SignalCard from "@/components/SignalCard";

const INSTRUMENTS = ["BANKNIFTY", "NIFTY"];

export default function FuturesPage() {
  const [signals, setSignals] = useState<Record<string, Signal>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled(INSTRUMENTS.map((name) => getFutures(name))).then((results) => {
      const s: Record<string, Signal> = {};
      const e: Record<string, string> = {};
      results.forEach((r, i) => {
        const name = INSTRUMENTS[i];
        if (r.status === "fulfilled") s[name] = r.value;
        else e[name] = r.reason instanceof ApiError ? r.reason.message : "Failed to load.";
      });
      setSignals(s);
      setErrors(e);
      setLoading(false);
    });
  }, []);

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-medium">Futures desk</h1>
      {loading && <p className="text-sm text-black/50">Computing live signals from Kite data…</p>}
      {INSTRUMENTS.map((name) => (
        <div key={name}>
          {signals[name] && <SignalCard sig={signals[name]} />}
          {errors[name] && <p className="text-sm text-red-700 dark:text-red-400">{name}: {errors[name]}</p>}
        </div>
      ))}
    </main>
  );
}
