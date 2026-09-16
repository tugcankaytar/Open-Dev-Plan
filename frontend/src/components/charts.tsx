import type { DailyActivity } from "../api/types";

const DAY_LABELS_TR = ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"];

/** Area + line chart of created-vs-completed tasks per day, computed
 * from real /api/stats/dashboard data — same shape as the design mockup,
 * but every point comes from `data`, not a hardcoded sample. */
export function WeeklyActivityChart({ data }: { data: DailyActivity[] }) {
  const width = 560;
  const height = 150;
  const padTop = 10;
  const padBottom = 20;
  const plotHeight = height - padTop - padBottom;

  const maxValue = Math.max(1, ...data.map((d) => Math.max(d.created, d.completed)));
  const stepX = data.length > 1 ? width / (data.length - 1) : 0;

  const yFor = (v: number) => padTop + plotHeight - (v / maxValue) * plotHeight;
  const completedPoints = data.map((d, i) => [i * stepX, yFor(d.completed)] as const);
  const createdPoints = data.map((d, i) => [i * stepX, yFor(d.created)] as const);

  const linePath = (points: readonly (readonly [number, number])[]) =>
    points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");

  const areaPath =
    linePath(completedPoints) +
    ` L${width},${height - padBottom} L0,${height - padBottom} Z`;

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={150} preserveAspectRatio="none">
        <defs>
          <linearGradient id="odp-area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6E56CF" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#6E56CF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <g stroke="#eef0f4" strokeWidth={1}>
          {[0.0, 0.33, 0.66, 1.0].map((f) => (
            <line key={f} x1={0} y1={padTop + plotHeight * f} x2={width} y2={padTop + plotHeight * f} />
          ))}
        </g>
        <path d={linePath(createdPoints)} fill="none" stroke="#c9c0f0" strokeWidth={2} strokeLinecap="round" strokeDasharray="1 7" />
        <path d={areaPath} fill="url(#odp-area-fill)" />
        <path d={linePath(completedPoints)} fill="none" stroke="#6E56CF" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
        {completedPoints.length > 0 && (
          <circle cx={completedPoints[completedPoints.length - 1][0]} cy={completedPoints[completedPoints.length - 1][1]} r={4} fill="#6E56CF" />
        )}
      </svg>
      <div className="mono faint" style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5 }}>
        {data.map((d) => (
          <span key={d.date}>{DAY_LABELS_TR[new Date(d.date).getDay()]}</span>
        ))}
      </div>
    </div>
  );
}

const STATUS_META: Record<string, { label: string; color: string }> = {
  todo: { label: "Yapılacak", color: "#6E56CF" },
  in_progress: { label: "Devam ediyor", color: "#3fd0e0" },
  blocked: { label: "Bloke", color: "#f2a63a" },
  done: { label: "Tamamlandı", color: "#d8dae2" },
};
const STATUS_ORDER = ["todo", "in_progress", "blocked", "done"];

/** Donut chart of task status counts, segments computed from real data. */
export function StatusDonutChart({ counts }: { counts: Record<string, number> }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;

  let offset = 0;
  const segments = STATUS_ORDER.map((key) => {
    const value = counts[key] ?? 0;
    const fraction = total > 0 ? value / total : 0;
    const length = fraction * circumference;
    const segment = { key, value, dash: `${length} ${circumference - length}`, dashOffset: -offset };
    offset += length;
    return segment;
  });

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
      <svg width={118} height={118} viewBox="0 0 140 140" style={{ flexShrink: 0 }}>
        <g transform="translate(70,70) rotate(-90)">
          <circle r={radius} fill="none" stroke="#eef0f4" strokeWidth={16} />
          {total === 0
            ? null
            : segments.map((s) =>
                s.value > 0 ? (
                  <circle
                    key={s.key}
                    r={radius}
                    fill="none"
                    stroke={STATUS_META[s.key].color}
                    strokeWidth={16}
                    strokeDasharray={s.dash}
                    strokeDashoffset={s.dashOffset}
                    strokeLinecap="round"
                  />
                ) : null
              )}
        </g>
        <text x={70} y={66} textAnchor="middle" fontFamily="IBM Plex Mono" fontSize={22} fontWeight={600} fill="#14161c">
          {total}
        </text>
        <text x={70} y={83} textAnchor="middle" fontFamily="IBM Plex Sans" fontSize={10} fill="#9aa0ad">
          görev
        </text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 9, fontSize: 12, flex: 1 }}>
        {STATUS_ORDER.map((key) => (
          <span key={key} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: STATUS_META[key].color }} />
            {STATUS_META[key].label}
            <b className="mono" style={{ marginLeft: "auto" }}>
              {counts[key] ?? 0}
            </b>
          </span>
        ))}
      </div>
    </div>
  );
}
