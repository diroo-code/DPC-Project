import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UploadPage } from "./UploadPage.jsx";

const uploadPhoto = vi.fn();

vi.mock("../lib/api.js", () => ({
  uploadPhoto: (...args) => uploadPhoto(...args),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <UploadPage />
    </MemoryRouter>,
  );
}

function imageFile(size, type = "image/jpeg", name = "photo.jpg") {
  return new File([new Uint8Array(size)], name, { type });
}

describe("UploadPage", () => {
  beforeEach(() => {
    uploadPhoto.mockReset();
  });

  it("rejects a file type the server would refuse, before sending it", async () => {
    renderPage();
    const input = screen.getByLabelText("Image");
    fireEvent.change(input, { target: { files: [imageFile(1024, "image/gif", "anim.gif")] } });
    expect(await screen.findByText(/Choose a JPEG, PNG or WebP image/)).toBeInTheDocument();
    expect(uploadPhoto).not.toHaveBeenCalled();
  });

  it("rejects a file larger than 5 MB", async () => {
    renderPage();
    const input = screen.getByLabelText("Image");
    fireEvent.change(input, { target: { files: [imageFile(5 * 1024 * 1024 + 1)] } });
    expect(await screen.findByText(/5 MB or smaller/)).toBeInTheDocument();
    expect(uploadPhoto).not.toHaveBeenCalled();
  });

  it("requires a file before submitting", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText(/Choose an image first/)).toBeInTheDocument();
  });

  it("sends a valid image with the chosen visibility and tags", async () => {
    uploadPhoto.mockResolvedValue({ id: "photo-1" });
    renderPage();

    fireEvent.change(screen.getByLabelText("Image"), {
      target: { files: [imageFile(2048)] },
    });
    fireEvent.change(screen.getByLabelText("Caption"), { target: { value: "Lake" } });
    fireEvent.click(screen.getByLabelText("Only me"));
    fireEvent.change(screen.getByLabelText("Tags"), { target: { value: "lake, sunset" } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => expect(uploadPhoto).toHaveBeenCalledTimes(1));
    expect(uploadPhoto.mock.calls[0][0]).toMatchObject({
      caption: "Lake",
      visibility: "owner",
      tags: "lake, sunset",
    });
  });

  it("shows the server error instead of a success state", async () => {
    uploadPhoto.mockRejectedValue(new Error("daily upload limit reached"));
    renderPage();
    fireEvent.change(screen.getByLabelText("Image"), { target: { files: [imageFile(2048)] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText(/daily upload limit reached/)).toBeInTheDocument();
  });
});
