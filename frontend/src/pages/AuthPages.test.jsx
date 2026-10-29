import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { LoginPage, RegisterPage } from "./AuthPages.jsx";

const authState = {
  status: "signed_out",
  token: null,
  profile: null,
  supabaseEnabled: false,
  devAuthAvailable: false,
  signIn: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  useDevToken: vi.fn(),
};

vi.mock("../lib/auth.jsx", () => ({
  useAuth: () => authState,
}));

describe("authentication screens without Supabase", () => {
  it("says authentication is unavailable instead of showing a dead form", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Authentication is not configured/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });

  it("explains that registration is blocked rather than pretending it works", () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Registration requires Supabase Auth/)).toBeInTheDocument();
    expect(screen.getByText(/blocked feature, not a working one/)).toBeInTheDocument();
  });
});
