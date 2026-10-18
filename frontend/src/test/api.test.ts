import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it } from "vitest";

import { getErrorMessage, getFieldErrors } from "@/lib/api";

function axiosError(status: number | null, data?: unknown, code?: string) {
  const config = { headers: new AxiosHeaders() };
  const response = status === null ? undefined : { status, data, statusText: "", headers: {}, config };
  return new AxiosError("fail", code, config, null, response as never);
}

describe("getErrorMessage", () => {
  it("prefers DRF's detail", () => {
    expect(getErrorMessage(axiosError(403, { detail: "Only support staff can perform this action." }))).toBe(
      "Only support staff can perform this action.",
    );
  });

  it("formats the first field error with a readable field name", () => {
    expect(getErrorMessage(axiosError(400, { category_id: ["Invalid pk."] }))).toBe("Category: Invalid pk.");
  });

  it("handles network errors and timeouts", () => {
    expect(getErrorMessage(axiosError(null))).toMatch(/Cannot reach the server/);
    expect(getErrorMessage(axiosError(null, undefined, "ECONNABORTED"))).toMatch(/timed out/);
  });

  it("never leaks raw server errors", () => {
    expect(getErrorMessage(axiosError(500, "<html>Traceback...</html>"))).toBe("The server had a problem. Please try again later.");
  });
});

describe("getFieldErrors", () => {
  it("maps DRF 400 responses to field messages", () => {
    expect(getFieldErrors(axiosError(400, { email: ["Already exists."], password: "Too short." }))).toEqual({
      email: "Already exists.",
      password: "Too short.",
    });
  });

  it("ignores non-400 errors", () => {
    expect(getFieldErrors(axiosError(500, { email: ["x"] }))).toEqual({});
  });
});
