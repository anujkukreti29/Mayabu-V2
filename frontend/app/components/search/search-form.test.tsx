import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { MemoryRouter } from "react-router";
import { SearchForm } from "~/components/search/search-form";
import { clearRecentSearches, pushRecentSearch } from "~/lib/search/recent-searches";

const navigateMock = vi.fn();
const searchSuggestMock = vi.fn();

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...(actual as Record<string, unknown>),
    useNavigate: () => navigateMock,
  };
});

vi.mock("~/lib/api/search", () => ({
  searchSuggest: (...args: unknown[]) => searchSuggestMock(...args) as Promise<unknown>,
}));

function renderForm(props: Partial<ComponentProps<typeof SearchForm>> = {}) {
  return render(
    <MemoryRouter>
      <SearchForm {...props} />
    </MemoryRouter>,
  );
}

describe("SearchForm smart suggestions", () => {
  beforeEach(() => {
    clearRecentSearches();
    navigateMock.mockReset();
    searchSuggestMock.mockReset();
    searchSuggestMock.mockResolvedValue({
      query: "",
      products: [],
      categories: [{ slug: "smartphone", label: "Smartphones" }],
      popular_queries: [],
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    clearRecentSearches();
    vi.useRealTimers();
  });

  it("shows recent searches and clears them", async () => {
    pushRecentSearch("galaxy s24");
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderForm();
    const input = screen.getByRole("combobox", { name: /search mayabu products/i });
    await user.click(input);
    expect(await screen.findByText("galaxy s24")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^clear$/i }));
    await waitFor(() => {
      expect(screen.queryByText("galaxy s24")).not.toBeInTheDocument();
    });
  });

  it("debounces suggest requests and keeps the latest query", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let resolveSlow: ((value: unknown) => void) | undefined;
    const slow = new Promise((resolve) => {
      resolveSlow = resolve;
    });

    searchSuggestMock.mockImplementation((q: string) => {
      const query = String(q || "").trim();
      if (query.length < 2) {
        return Promise.resolve({
          query: "",
          products: [],
          categories: [],
          popular_queries: [],
        });
      }
      if (query === "iph") return slow;
      if (query.startsWith("iphone")) {
        return Promise.resolve({
          query: "iphone",
          products: [
            {
              id: "p1",
              title: "Apple iPhone 15",
              brand: "Apple",
              category: "smartphone",
              image_url: null,
              best_price: 69999,
              best_platform: "amazon",
              offer_count: 3,
              display_specs: { ram_gb: 8, storage_gb: 128 },
              specs: {},
              model_codes: [],
            },
          ],
          categories: [{ slug: "smartphone", label: "Smartphones" }],
          popular_queries: [],
        });
      }
      return Promise.resolve({
        query,
        products: [],
        categories: [],
        popular_queries: [],
      });
    });

    renderForm();
    const input = screen.getByRole("combobox", { name: /search mayabu products/i });
    await user.click(input);
    await user.type(input, "iph");
    await vi.advanceTimersByTimeAsync(230);
    await user.type(input, "one");
    await vi.advanceTimersByTimeAsync(230);

    resolveSlow?.({
      query: "iph",
      products: [
        {
          id: "stale",
          title: "Stale Product",
          brand: null,
          category: "smartphone",
          image_url: null,
          best_price: 1000,
          best_platform: null,
          offer_count: 1,
          display_specs: {},
          specs: {},
          model_codes: [],
        },
      ],
      categories: [],
      popular_queries: [],
    });

    expect(await screen.findByText("Apple iPhone 15")).toBeInTheDocument();
    expect(screen.queryByText("Stale Product")).not.toBeInTheDocument();
    expect(screen.getByText("₹69,999")).toBeInTheDocument();
  });

  it("navigates product suggestion with Enter after arrow keys", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    searchSuggestMock.mockResolvedValue({
      query: "galaxy",
      products: [
        {
          id: "phone-1",
          title: "Samsung Galaxy S24",
          brand: "Samsung",
          category: "smartphone",
          image_url: null,
          best_price: 54999,
          best_platform: "flipkart",
          offer_count: 2,
          display_specs: { ram_gb: 8, storage_gb: 256 },
          specs: {},
          model_codes: [],
        },
      ],
      categories: [],
      popular_queries: [],
    });
    renderForm();
    const input = screen.getByRole("combobox", { name: /search mayabu products/i });
    await user.click(input);
    await user.type(input, "galaxy");
    await vi.advanceTimersByTimeAsync(230);
    expect(await screen.findByText("Samsung Galaxy S24")).toBeInTheDocument();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(navigateMock).toHaveBeenCalled();
    const href = String(navigateMock.mock.calls.at(-1)?.[0] ?? "");
    expect(href).toContain("/products/phone-1/");
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderForm();
    const input = screen.getByRole("combobox", { name: /search mayabu products/i });
    await user.click(input);
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    });
  });

  it("omits popular section when unsupported", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    searchSuggestMock.mockResolvedValue({
      query: "",
      products: [],
      categories: [],
      popular_queries: [],
    });
    renderForm();
    const input = screen.getByRole("combobox", { name: /search mayabu products/i });
    await user.click(input);
    await waitFor(() => {
      expect(searchSuggestMock).toHaveBeenCalled();
    });
    expect(screen.queryByLabelText("Popular searches")).not.toBeInTheDocument();
  });

  it("falls back gracefully when suggest fails", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    searchSuggestMock.mockRejectedValue(new Error("network"));
    renderForm();
    const input = screen.getByRole("combobox", { name: /search mayabu products/i });
    await user.click(input);
    await user.type(input, "iphone");
    await vi.advanceTimersByTimeAsync(230);
    expect(await screen.findByText(/suggestions unavailable/i)).toBeInTheDocument();
    const listbox = screen.getByRole("listbox");
    expect(within(listbox).getByText(/press enter to search/i)).toBeInTheDocument();
  });

  it("keeps unique combobox and listbox ids when multiple forms mount", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <MemoryRouter>
        <SearchForm inputId="nav-search" compact />
        <SearchForm />
      </MemoryRouter>,
    );
    const inputs = screen.getAllByRole("combobox", { name: /search mayabu products/i });
    expect(inputs).toHaveLength(2);
    const inputIds = inputs.map((el) => el.id);
    expect(new Set(inputIds).size).toBe(2);
    const controlIds = inputs.map((el) => el.getAttribute("aria-controls"));
    expect(controlIds.every(Boolean)).toBe(true);
    expect(new Set(controlIds).size).toBe(2);

    await user.click(inputs[0]!);
    const firstListbox = await screen.findByRole("listbox");
    expect(firstListbox.id).toBe(controlIds[0]);
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    });

    await user.click(inputs[1]!);
    const secondListbox = await screen.findByRole("listbox");
    expect(secondListbox.id).toBe(controlIds[1]);
    expect(secondListbox.id).not.toBe(controlIds[0]);
  });
});
