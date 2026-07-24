"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Brief" },
  { href: "/futures", label: "Futures" },
  { href: "/stock", label: "Stock" },
  { href: "/paper", label: "Paper trading" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="border-b border-black/10 dark:border-white/10 sticky top-0 bg-white/90 dark:bg-black/90 backdrop-blur z-10">
      <div className="max-w-4xl mx-auto flex items-center gap-1 px-4 h-12">
        <span className="font-medium text-sm mr-4">MarketDawn</span>
        {LINKS.map((l) => {
          const active = pathname === l.href;
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`text-sm px-3 py-1.5 rounded-md ${
                active
                  ? "bg-black/10 dark:bg-white/15 font-medium"
                  : "text-black/60 dark:text-white/60 hover:bg-black/5 dark:hover:bg-white/10"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
