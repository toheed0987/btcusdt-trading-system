import clsx from "clsx";

export default function MetricCard({
  label,
  value,
  sub,
  colorClass,
}: {
  label: string;
  value: string;
  sub?: string;
  colorClass?: string;
}) {
  return (
    <div className="card">
      <div className="metric-label">{label}</div>
      <div className={clsx("metric-value", colorClass)}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  );
}
