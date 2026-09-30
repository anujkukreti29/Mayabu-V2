import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "~/components/auth/auth-provider";
import { Header } from "~/components/layout/header";

function renderHeader(path: string) {
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <AuthProvider>
            <Header />
          </AuthProvider>
        ),
      },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

describe("Header", () => {
  it("hides compact nav search on the homepage", () => {
    renderHeader("/");
    expect(document.getElementById("nav-search")).toBeNull();
  });

  it("shows substantial nav search on internal pages", () => {
    renderHeader("/laptops");
    const input = document.getElementById("nav-search");
    expect(input).toBeInTheDocument();
    const form = input?.closest("form");
    expect(form).toBeTruthy();
    expect(form?.querySelector('button[type="submit"]')).toBeInTheDocument();
  });

  it("keeps navbar search as the desktop query control on Search", () => {
    renderHeader("/search?q=asus");
    const input = document.getElementById("nav-search");
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue("asus");
  });

  it("exposes Categories, Compare, How It Works, and account icons", async () => {
    const user = userEvent.setup();
    renderHeader("/");
    expect(screen.getByRole("button", { name: /Categories/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Discover" })).toBeNull();
    expect(screen.getByRole("link", { name: "Compare" })).toHaveAttribute("href", "/compare");
    expect(screen.getByRole("link", { name: "How It Works" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Wishlist/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Profile" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Profile" }));
    expect(screen.getByRole("menuitem", { name: "Sign in" })).toBeVisible();
    expect(screen.getByRole("menuitem", { name: "Create account" })).toBeVisible();
  });

  it("renders the Mayabu logo linking home", () => {
    renderHeader("/");
    const logo = screen.getByRole("link", { name: "Mayabu home" });
    expect(logo).toHaveAttribute("href", "/");
    expect(logo.querySelector("img")).toHaveAttribute("alt", "Mayabu");
  });
});
