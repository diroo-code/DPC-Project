import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, mediaUrl, request, setTokenProvider } from "./api.js";

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? "" : JSON.stringify(body)),
  };
}

describe("api client", () => {
  beforeEach(() => {
    setTokenProvider(() => "token-123");
    global.fetch = vi.fn();
  });

  afterEach(() => {
    setTokenProvider(() => null);
    vi.restoreAllMocks();
  });

  it("attaches the bearer token", async () => {
    global.fetch.mockResolvedValue(jsonResponse(200, { ok: true }));
    await request("/api/v1/auth/me");
    const [, options] = global.fetch.mock.calls[0];
    expect(options.headers.Authorization).toBe("Bearer token-123");
  });

  it("returns null for 204 responses", async () => {
    global.fetch.mockResolvedValue(jsonResponse(204));
    await expect(request("/api/v1/photos/1", { method: "DELETE" })).resolves.toBeNull();
  });

  it("surfaces a string detail from the API", async () => {
    global.fetch.mockResolvedValue(jsonResponse(403, { detail: "not allowed" }));
    await expect(request("/api/v1/photos")).rejects.toMatchObject({
      status: 403,
      message: "not allowed",
    });
  });

  it("joins FastAPI validation errors into one message", async () => {
    global.fetch.mockResolvedValue(
      jsonResponse(422, { detail: [{ msg: "field required" }, { msg: "bad value" }] }),
    );
    await expect(request("/api/v1/photos")).rejects.toMatchObject({
      status: 422,
      message: "field required, bad value",
    });
  });

  it("reports an unreachable server without leaking internals", async () => {
    global.fetch.mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await request("/api/v1/photos").catch((problem) => problem);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.message).toMatch(/Could not reach the server/);
  });

  it("prefixes relative media paths only", () => {
    expect(mediaUrl("/media/a.jpg?x=1")).toBe("/media/a.jpg?x=1");
    expect(mediaUrl("https://example.test/a.jpg")).toBe("https://example.test/a.jpg");
    expect(mediaUrl(null)).toBeNull();
  });
});
