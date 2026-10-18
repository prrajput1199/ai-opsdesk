import {
  BarChart3,
  BookOpen,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Menu,
  PlusCircle,
  ScrollText,
  Settings2,
  Sparkles,
  Ticket,
  UserCircle,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState, type ComponentType } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useLogout } from "@/api/auth";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@/lib/types";
import { cn, initials } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  roles?: Role[];
  end?: boolean;
}

const NAV: { section?: string; items: NavItem[] }[] = [
  {
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
      { to: "/tickets", label: "Tickets", icon: Ticket, end: true },
      { to: "/tickets/new", label: "New ticket", icon: PlusCircle, roles: ["CUSTOMER"] },
    ],
  },
  {
    section: "Knowledge",
    items: [
      { to: "/kb", label: "Knowledge base", icon: BookOpen, end: true },
      { to: "/kb/ask", label: "Search & Ask AI", icon: Sparkles },
    ],
  },
  {
    section: "Insights",
    items: [{ to: "/analytics", label: "Analytics", icon: BarChart3, roles: ["ADMIN", "AGENT"] }],
  },
  {
    section: "Administration",
    items: [
      { to: "/admin/users", label: "Users & agents", icon: Users, roles: ["ADMIN"] },
      { to: "/admin/settings", label: "Categories & SLA", icon: Settings2, roles: ["ADMIN"] },
      { to: "/admin/audit", label: "Audit log", icon: ScrollText, roles: ["ADMIN"] },
    ],
  },
];

const ROLE_LABEL: Record<Role, string> = { ADMIN: "Admin", AGENT: "Agent", CUSTOMER: "Customer" };

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
        <Sparkles className="size-4" />
      </div>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-slate-900">AI OpsDesk</p>
        <p className="text-[11px] text-slate-500">Support intelligence</p>
      </div>
    </div>
  );
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4" aria-label="Main">
      {NAV.map((group, i) => {
        const items = group.items.filter((item) => !item.roles || (user && item.roles.includes(user.role)));
        if (!items.length) return null;
        return (
          <div key={i}>
            {group.section && (
              <p className="mb-1.5 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{group.section}</p>
            )}
            <ul className="space-y-0.5">
              {items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                        isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                      )
                    }
                  >
                    <item.icon className="size-4 shrink-0" />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

export function AppLayout() {
  const { user } = useAuth();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMobileOpen(false), [location.pathname]);

  async function handleLogout() {
    await logout.mutateAsync().catch(() => undefined);
    toast.success("You have been logged out.");
    navigate("/login", { replace: true });
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow">
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-16 items-center border-b border-slate-100 px-3">
          <Brand />
        </div>
        <SidebarNav />
        <div className="border-t border-slate-100 p-3 text-[11px] text-slate-400">Signed in as {ROLE_LABEL[user.role]}</div>
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-white shadow-xl animate-fade-in">
            <div className="flex h-16 items-center justify-between border-b border-slate-100 px-3">
              <Brand />
              <Button variant="ghost" size="icon" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
                <X />
              </Button>
            </div>
            <SidebarNav onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu />
          </Button>
          <div className="lg:hidden">
            <Brand />
          </div>
          <div className="ml-auto flex items-center gap-2">
            {user.role === "CUSTOMER" && (
              <Button size="sm" className="hidden sm:inline-flex" onClick={() => navigate("/tickets/new")}>
                <PlusCircle /> New ticket
              </Button>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 text-left hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
                  <span className="flex size-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                    {initials(user.name)}
                  </span>
                  <span className="hidden text-sm leading-tight sm:block">
                    <span className="block font-medium text-slate-900">{user.name}</span>
                    <span className="block text-xs text-slate-500">{ROLE_LABEL[user.role]}</span>
                  </span>
                  <ChevronDown className="size-4 text-slate-400" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{user.email}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => navigate("/profile")}>
                  <UserCircle /> Profile & settings
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={handleLogout} className="text-red-600">
                  <LogOut /> Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
