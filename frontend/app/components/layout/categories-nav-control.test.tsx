import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CategoriesNavControl } from "~/components/layout/categories-nav-control";

function mockMatchMedia(hoverFine: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: hoverFine && query.includes("hover: hover"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

function renderControl() {
  const router = createMemoryRouter([{ path: "/", element: <CategoriesNavControl /> }], {
    initialEntries: ["/"],
  });
  return render(<RouterProvider router={router} />);
}

describe("CategoriesNavControl", () => {
  beforeEach(() => {
    mockMatchMedia(true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens on click and closes on Escape", async () => {
    const user = userEvent.setup();
    renderControl();
    const trigger = screen.getByRole("button", { name: /Categories/i });
    await user.click(trigger);
    expect(screen.getByRole("navigation", { name: "Product categories" })).toBeVisible();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("navigation", { name: "Product categories" }),
    ).not.toBeInTheDocument();
  });

  it("opens on keyboard ArrowDown", async () => {
    const user = userEvent.setup();
    renderControl();
    const trigger = screen.getByRole("button", { name: /Categories/i });
    trigger.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("navigation", { name: "Product categories" })).toBeVisible();
  });
});
