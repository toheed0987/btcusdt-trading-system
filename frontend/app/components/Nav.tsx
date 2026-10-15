"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/monitoring", label: "Model Monitoring" },
  { href: "/retraining", label: "Retraining" },
  { href: "/backtest", label: "Backtesting" },
  { href: "/admin", label: "Admin Panel" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="border-b border-border bg-panel px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-6">
        <span className="font-semibold text-lg tracking-tight">
          ₿ BTC/USDT <span className="text-accent">Signal System</span>
        </span>
        <div className="flex gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={clsx(
                "px-3 py-1.5 rounded-md text-sm transition-colors",
                pathname === l.href
                  ? "bg-accent/20 text-accent font-medium"
                  : "text-gray-400 hover:text-white hover:bg-white/5"
              )}
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
      <span className="text-xs text-gray-500 max-w-xs text-right hidden md:block">
        All outputs are probability-based estimates, not certainties or financial advice.
      </span>
    </nav>
  );
}
