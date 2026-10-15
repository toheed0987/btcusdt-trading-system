import type { Metadata } from "next";
import "./globals.css";
import Nav from "./components/Nav";

export const metadata: Metadata = {
  title: "BTC/USDT Probabilistic Trading System",
  description: "Probability-based BTC/USDT signal dashboard — not financial advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-gray-100">
        <Nav />
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
