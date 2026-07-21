import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { Header } from "~/components/layout/header";

describe("Header", () => {
  it("exposes accessible mobile menu controls", async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter([{ path: "*", element: <Header /> }], {
      initialEntries: ["/"],
    });
    render(<RouterProvider router={router} />);
    const button = screen.getByRole("button", { name: "Open menu" });
    await user.click(button);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close menu" })).toBeInTheDocument();
  });
});
