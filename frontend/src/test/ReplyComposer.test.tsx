import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReplyComposer } from "@/components/tickets/ReplyComposer";
import { api } from "@/lib/api";

import { makeUser, renderWithProviders } from "./utils";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } };
});

describe("ReplyComposer", () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset().mockResolvedValue({ data: { id: 1 } });
  });

  it("hides the internal-note option for customers", () => {
    renderWithProviders(<ReplyComposer ticketId={7} canAddInternalNote={false} />, { user: makeUser("CUSTOMER") });
    expect(screen.queryByRole("tab", { name: /internal note/i })).not.toBeInTheDocument();
  });

  it("sends an internal note when staff choose that mode", async () => {
    renderWithProviders(<ReplyComposer ticketId={7} canAddInternalNote />, { user: makeUser("AGENT") });
    await userEvent.click(screen.getByRole("tab", { name: /internal note/i }));
    await userEvent.type(screen.getByLabelText("Internal note"), "Checked the logs");
    await userEvent.click(screen.getByRole("button", { name: /add note/i }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/tickets/7/comments/", { body: "Checked the logs", is_internal: true }),
    );
  });

  it("does not send empty messages", async () => {
    renderWithProviders(<ReplyComposer ticketId={7} canAddInternalNote={false} />, { user: makeUser("CUSTOMER") });
    expect(screen.getByRole("button", { name: /send reply/i })).toBeDisabled();
  });

  it("can be prefilled with an AI suggestion", async () => {
    const onConsumed = vi.fn();
    renderWithProviders(<ReplyComposer ticketId={7} canAddInternalNote prefill="Suggested text" onPrefillConsumed={onConsumed} />, {
      user: makeUser("AGENT"),
    });
    expect(screen.getByLabelText("Reply")).toHaveValue("Suggested text");
    expect(onConsumed).toHaveBeenCalled();
  });
});
