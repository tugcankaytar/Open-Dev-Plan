import type { Meeting } from "../api/types";

const WEEKDAY_LABELS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const MAX_EVENTS_PER_CELL = 3;

function startOfMonthGrid(year: number, month: number): Date {
  const first = new Date(year, month, 1);
  // getDay(): 0=Sunday..6=Saturday; shift so Monday=0 for a Mon-start grid.
  const offset = (first.getDay() + 6) % 7;
  const start = new Date(year, month, 1 - offset);
  return start;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export default function MonthCalendar({
  year,
  month,
  meetings,
  onSelectMeeting,
}: {
  year: number;
  month: number; // 0-indexed
  meetings: Meeting[];
  onSelectMeeting: (id: string) => void;
}) {
  const gridStart = startOfMonthGrid(year, month);
  const today = new Date();

  const days: Date[] = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    return d;
  });

  const eventsByDay = new Map<string, Meeting[]>();
  for (const m of meetings) {
    const d = new Date(m.start_utc);
    const key = d.toDateString();
    const list = eventsByDay.get(key) ?? [];
    list.push(m);
    eventsByDay.set(key, list);
  }

  return (
    <div className="month-grid">
      {WEEKDAY_LABELS.map((label) => (
        <div key={label} className="month-weekday">
          {label}
        </div>
      ))}
      {days.map((day) => {
        const dayMeetings = (eventsByDay.get(day.toDateString()) ?? []).sort((a, b) =>
          a.start_utc.localeCompare(b.start_utc)
        );
        const outside = day.getMonth() !== month;
        const isToday = isSameDay(day, today);
        const extra = dayMeetings.length - MAX_EVENTS_PER_CELL;

        return (
          <div key={day.toISOString()} className={`month-cell${outside ? " outside" : ""}${isToday ? " today" : ""}`}>
            <span className="month-cell-date">{day.getDate()}</span>
            {dayMeetings.slice(0, MAX_EVENTS_PER_CELL).map((m) => (
              <div
                key={m.id}
                className="month-event"
                title={`${m.title} — ${new Date(m.start_utc).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}`}
                onClick={() => onSelectMeeting(m.id)}
              >
                {new Date(m.start_utc).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}{" "}
                {m.title}
              </div>
            ))}
            {extra > 0 && <div className="faint small">+{extra} daha</div>}
          </div>
        );
      })}
    </div>
  );
}
