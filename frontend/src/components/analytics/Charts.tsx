import { format, parseISO } from "date-fns";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART } from "@/lib/constants";
import type { AgentWorkload, CategoryBreakdown, ResolutionTime, Trends } from "@/lib/types";

const axis = { fontSize: 12, fill: "#64748b" };
const grid = <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />;
const tooltipStyle = { borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 4px 12px rgb(15 23 42 / 0.08)" };

export function TrendChart({ data, height = 260 }: { data: Trends["series"]; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label="Tickets created and resolved per day">
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="createdFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.primary} stopOpacity={0.25} />
              <stop offset="100%" stopColor={CHART.primary} stopOpacity={0} />
            </linearGradient>
          </defs>
          {grid}
          <XAxis dataKey="date" tick={axis} tickLine={false} axisLine={false} minTickGap={24} tickFormatter={(d) => format(parseISO(d), "d MMM")} />
          <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={(d) => format(parseISO(String(d)), "EEE, d MMM yyyy")} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Area type="monotone" dataKey="created" name="Created" stroke={CHART.primary} strokeWidth={2} fill="url(#createdFill)" />
          <Area type="monotone" dataKey="resolved" name="Resolved" stroke={CHART.secondary} strokeWidth={2} fill="transparent" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CategoryChart({ data, height = 260 }: { data: CategoryBreakdown["categories"]; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label="Tickets by category">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
          <XAxis type="number" allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey="category" width={110} tick={axis} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f1f5f9" }} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="total" name="Total" fill={CHART.primary} radius={[0, 4, 4, 0]} barSize={14} />
          <Bar dataKey="active" name="Active" fill={CHART.warning} radius={[0, 4, 4, 0]} barSize={14} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PriorityChart({ data, height = 220 }: { data: CategoryBreakdown["priorities"]; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label="Tickets by priority">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          {grid}
          <XAxis dataKey="label" tick={axis} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f1f5f9" }} />
          <Bar dataKey="total" name="Tickets" radius={[4, 4, 0, 0]} barSize={36}>
            {data.map((d) => (
              <Cell key={d.priority} fill={CHART.priority[d.priority]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ResolutionChart({ data, height = 220 }: { data: ResolutionTime["distribution"]; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label="Resolution time distribution">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          {grid}
          <XAxis dataKey="bucket" tick={axis} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f1f5f9" }} />
          <Bar dataKey="count" name="Resolved tickets" fill={CHART.secondary} radius={[4, 4, 0, 0]} barSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function WorkloadChart({ data, height = 280 }: { data: AgentWorkload["agents"]; height?: number }) {
  const rows = data.map((a) => ({
    name: a.name,
    open: Math.max(a.active - a.in_progress - a.waiting_for_customer, 0),
    in_progress: a.in_progress,
    waiting: a.waiting_for_customer,
  }));
  return (
    <div style={{ height }} role="img" aria-label="Active tickets per agent">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          {grid}
          <XAxis dataKey="name" tick={axis} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f1f5f9" }} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="open" stackId="a" name="Open" fill={CHART.primary} barSize={32} />
          <Bar dataKey="in_progress" stackId="a" name="In progress" fill="#8b5cf6" barSize={32} />
          <Bar dataKey="waiting" stackId="a" name="Waiting" fill={CHART.warning} radius={[4, 4, 0, 0]} barSize={32} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
