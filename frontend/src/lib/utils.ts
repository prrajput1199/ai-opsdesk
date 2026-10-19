import { clsx, type ClassValue } from "clsx";
import { format, formatDistanceToNowStrict, isValid, parseISO } from "date-fns";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const d = typeof value === "string" ? parseISO(value) : value;
  return isValid(d) ? d : null;
}

export function formatDateTime(value: string | null | undefined) {
  const d = toDate(value);
  return d ? format(d, "d MMM yyyy, HH:mm") : "—";
}

export function formatDate(value: string | null | undefined) {
  const d = toDate(value);
  return d ? format(d, "d MMM yyyy") : "—";
}

export function timeAgo(value: string | null | undefined) {
  const d = toDate(value);
  return d ? formatDistanceToNowStrict(d, { addSuffix: true }) : "—";
}

export function formatHours(hours: number | null | undefined) {
  if (hours === null || hours === undefined) return "—";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} days`;
}

export function initials(name: string | null | undefined) {
  return (typeof name === "string" ? name : "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

/** ISO date (YYYY-MM-DD) n days before today, in local time. */
export function isoDaysAgo(days: number) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return format(d, "yyyy-MM-dd");
}
