import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { isoDaysAgo } from "@/lib/utils";

export interface Range {
  date_from?: string;
  date_to?: string;
}

const PRESETS = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
];

export function DateRangePicker({ value, onChange }: { value: Range; onChange: (r: Range) => void }) {
  const preset = PRESETS.find((p) => value.date_from === isoDaysAgo(p.days - 1) && value.date_to === isoDaysAgo(0));
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select
        aria-label="Date range preset"
        className="w-40"
        value={preset ? String(preset.days) : "custom"}
        onChange={(e) => {
          const days = Number(e.target.value);
          if (days) onChange({ date_from: isoDaysAgo(days - 1), date_to: isoDaysAgo(0) });
        }}
      >
        {PRESETS.map((p) => (
          <option key={p.days} value={p.days}>{p.label}</option>
        ))}
        <option value="custom" disabled>Custom range</option>
      </Select>
      <Input type="date" aria-label="From" className="w-[150px]" value={value.date_from ?? ""} max={value.date_to}
        onChange={(e) => onChange({ ...value, date_from: e.target.value })} />
      <span className="text-sm text-slate-400">to</span>
      <Input type="date" aria-label="To" className="w-[150px]" value={value.date_to ?? ""} min={value.date_from}
        onChange={(e) => onChange({ ...value, date_to: e.target.value })} />
    </div>
  );
}
