import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FeedPage } from "./FeedPage.jsx";

const listPhotos = vi.fn();
const searchPhotos = vi.fn();
const photoUrl = vi.fn();

vi.mock("../lib/api.js", () => ({
  listPhotos: (...args) => listPhotos(...args),
  searchPhotos: (...args) => searchPhotos(...args),
  photoUrl: (...args) => photoUrl(...args),
  mediaUrl: (path) => path,
}));

const photo = {
  id: "p1",
  owner_id: "u1",
  owner_username: "alice",
  caption: "Lake at dusk",
  mime_type: "image/jpeg",
  size_bytes: 2048,
  visibility: "friends",
  created_at: "2026-10-29T06:00:00Z",
  comment_count: 2,
  tags: ["lake"],
};

function renderFeed(props = {}) {
  return render(
    <MemoryRouter>
      <FeedPage {...props} />
    </MemoryRouter>,
  );
}

describe("FeedPage", () => {
  beforeEach(() => {
    listPhotos.mockReset();
    searchPhotos.mockReset();
    photoUrl.mockReset();
    photoUrl.mockResolvedValue({ url: "/media/p1.jpg?exp=1&sig=x" });
  });

  it("shows an empty state with a way forward when there are no photos", async () => {
    listPhotos.mockResolvedValue({ items: [], total: 0, has_more: false });
    renderFeed();
    expect(await screen.findByText("Nothing here yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload a photo" })).toBeInTheDocument();
  });

  it("renders photo captions, owner and tags from the API", async () => {
    listPhotos.mockResolvedValue({ items: [photo], total: 1, has_more: false });
    renderFeed();
    expect(await screen.findByText("Lake at dusk")).toBeInTheDocument();
    expect(screen.getByText(/@alice/)).toBeInTheDocument();
    expect(screen.getByText("lake")).toBeInTheDocument();
  });

  it("surfaces a permission or network error instead of an empty page", async () => {
    listPhotos.mockRejectedValue(new Error("Your session has expired."));
    renderFeed();
    expect(await screen.findByText("Your session has expired.")).toBeInTheDocument();
  });

  it("does not query search without a term", async () => {
    renderFeed({ searchMode: true });
    expect(await screen.findByText("No matching photos")).toBeInTheDocument();
    expect(searchPhotos).not.toHaveBeenCalled();
  });
});
