import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PriorityBadge, SLABadge, StatusBadge } from "@/components/tickets/badges";

describe("ticket badges", () => {
  it("shows human labels for status and priority", () => {
    render(
      <>
        <StatusBadge status="WAITING_FOR_CUSTOMER" />
        <PriorityBadge priority="URGENT" />
      </>,
    );
    expect(screen.getByText("Waiting for Customer")).toBeInTheDocument();
    expect(screen.getByText("Urgent")).toBeInTheDocument();
  });

  it("makes SLA breaches visually distinct", () => {
    render(<SLABadge status="breached" />);
    const badge = screen.getByText("Breached");
    expect(badge.className).toMatch(/red/);
    expect(badge).toHaveAttribute("title", "SLA: Breached");
  });
});
