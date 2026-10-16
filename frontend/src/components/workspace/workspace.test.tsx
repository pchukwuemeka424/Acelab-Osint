import { fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import { describe, expect, it, vi } from "vitest"
import type { EntityRecord } from "../../api/types"
import { accountVisible, resultScreen } from "../../lib/format"
import { DetailsPanel } from "./DetailsPanel"
import { CampaignPanel } from "./CampaignPanel"
import { EmailScreen } from "./EmailScreen"
import { GraphSearch } from "./GraphSearch"

const entity = (id: string, name: string): EntityRecord => ({
  id,
  entity_type: "domain",
  display_value: name,
  normalized_value: name,
  risk_state: "contextual",
  degree: 1,
  pos_x: 0,
  pos_y: 0,
  metadata: { registrar: "Example Registrar LLC", registered_at: "2020-01-02", expires_at: "2024-01-02", email: "", ip: "198.51.100.8", organization: "Demonstration Holdings" },
  first_observed: null,
  last_observed: null,
  source_name: "demonstration",
  retrieved_at: "2026-10-16T00:00:00Z",
  observed_at: "2020-01-02T00:00:00Z",
  verification_status: "observed",
  observation_id: "obs-1",
})

function renderPanel(items: EntityRecord[], extra: Partial<Parameters<typeof DetailsPanel>[0]> = {}) {
  const onSort = vi.fn()
  const onTab = vi.fn()
  const onSearch = vi.fn()
  const onExport = vi.fn()
  const onClose = vi.fn()
  const onFocus = vi.fn()
  render(
    <DetailsPanel
      investigationId="inv-1"
      counts={{ domain: items.length, ip: 0, certificate: 0, ssh: 0, contact: 0, file: 0, hypothesis: 0, more: 0 }}
      tab="domain"
      sort="domain"
      items={items}
      selectedId={null}
      edge={null}
      status="ready"
      error=""
      onTab={onTab}
      onSort={onSort}
      onSearch={onSearch}
      onExport={onExport}
      onClose={onClose}
      onFocus={onFocus}
      {...extra}
    />,
  )
  return { onSort, onTab, onSearch, onExport, onClose, onFocus }
}

describe("investigation workspace", () => {
  it("shows a scanner registration and a failed-scan note", () => {
    const site = entity("site-1", "Instagram")
    site.entity_type = "account"
    site.metadata = {
      lead: "scanner",
      category: "social",
      status: "Registered",
      url: "https://www.instagram.com/analyst/",
      platform: "Instagram",
      extra: { followers: "12", bio: "Public bio" },
    }
    render(<EmailScreen address="Jane Doe" hits={[site]} loading={false} />)
    expect(screen.getByRole("heading", { name: "Registration log" })).toBeInTheDocument()
    expect(screen.getByLabelText("Registration globe")).toBeInTheDocument()
    expect(screen.getByText("Instagram")).toBeInTheDocument()
    expect(screen.getByText("social")).toBeInTheDocument()
    expect(screen.getByText("Registered")).toBeInTheDocument()
    expect(screen.getByText("12")).toBeInTheDocument()
    expect(screen.getByText("Public bio")).toBeInTheDocument()

    render(
      <EmailScreen
        address="analyst@example.test"
        hits={[]}
        loading={false}
        notice="The public registration scan could not be completed."
      />,
    )
    expect(screen.getByText("The public registration scan could not be completed.")).toBeInTheDocument()
  })

  it("opens a name on a different screen from a website", () => {
    expect(resultScreen("name")).toBe("name")
    expect(resultScreen("domain")).toBe("website")
    expect(resultScreen("url")).toBe("website")
    expect(accountVisible("account")).toBe(true)
    expect(accountVisible("domain")).toBe(false)
  })

  it("submits a search on enter", () => {
    const onSubmit = vi.fn()
    render(<GraphSearch value="" busy={false} error="" onSubmit={onSubmit} />)
    const input = screen.getByLabelText("Investigate indicator")
    fireEvent.change(input, { target: { value: "portal.example.test" } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(onSubmit).toHaveBeenCalledWith("portal.example.test")
  })

  it("shows a validation error for an empty search", () => {
    render(<GraphSearch value="" busy={false} error="" onSubmit={vi.fn()} />)
    fireEvent.submit(screen.getByLabelText("Investigate indicator").closest("form")!)
    expect(screen.getByText(/Enter a domain/)).toBeInTheDocument()
  })

  it("renders records in the given order and sorts when asked", () => {
    const { onSort } = renderPanel([entity("b", "b.example.test"), entity("a", "a.example.test")])
    const names = screen.getAllByRole("button", { name: /example.test/ }).map((node) => node.textContent)
    expect(names).toEqual(["b.example.test", "a.example.test"])
    fireEvent.click(screen.getByRole("button", { name: "Exp date" }))
    expect(onSort).toHaveBeenCalledWith("exp_date")
  })

  it("filters tabs, collapses, and exports", () => {
    const { onTab, onClose, onExport, onFocus } = renderPanel([entity("a", "a.example.test")])
    for (const label of ["Whois", "SEO", "Logo", "Pages", "More"]) {
      expect(screen.getByRole("tab", { name: new RegExp(label) })).toBeVisible()
    }
    fireEvent.click(screen.getByRole("tab", { name: /SEO/ }))
    expect(onTab).toHaveBeenCalledWith("seo")
    fireEvent.click(screen.getByRole("tab", { name: /Logo/ }))
    expect(onTab).toHaveBeenCalledWith("logo")
    fireEvent.click(screen.getByRole("tab", { name: /IP/ }))
    expect(onTab).toHaveBeenCalledWith("ip")
    fireEvent.click(screen.getByRole("button", { name: "a.example.test" }))
    expect(onFocus).toHaveBeenCalledWith("a")
    fireEvent.click(screen.getByRole("button", { name: "Export records" }))
    expect(onExport).toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Close details" }))
    expect(onClose).toHaveBeenCalled()
  })

  it("shows empty and error states", () => {
    renderPanel([], { status: "ready" })
    expect(screen.getByText("No records in this category.")).toBeInTheDocument()
    renderPanel([], { status: "error", error: "Could not load records." })
    expect(screen.getByText("Could not load records.")).toBeInTheDocument()
  })

  it("collapses and reopens the details panel", () => {
    function Harness() {
      const [open, setOpen] = useState(true)
      return (
        <>
          {open && (
            <DetailsPanel
              investigationId="inv-1"
              counts={{ domain: 1 }}
              tab="domain"
              sort="domain"
              items={[entity("a", "a.example.test")]}
              selectedId={null}
              edge={null}
              status="ready"
              error=""
              onTab={vi.fn()}
              onSort={vi.fn()}
              onSearch={vi.fn()}
              onExport={vi.fn()}
              onClose={() => setOpen(false)}
              onFocus={vi.fn()}
            />
          )}
          <button type="button" aria-label={open ? "Collapse details" : "Open details"} onClick={() => setOpen((value) => !value)}>
            toggle
          </button>
        </>
      )
    }
    render(<Harness />)
    expect(screen.getByRole("heading", { name: "Nodes details" })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Collapse details" }))
    expect(screen.queryByRole("heading", { name: "Nodes details" })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Open details" }))
    expect(screen.getByRole("heading", { name: "Nodes details" })).toBeInTheDocument()
  })

  it("filters records from the panel search", () => {
    const { onSearch } = renderPanel([entity("a", "a.example.test")])
    fireEvent.click(screen.getByRole("button", { name: "Search records" }))
    fireEvent.change(screen.getByLabelText("Filter records"), { target: { value: "a.example" } })
    expect(onSearch).toHaveBeenCalledWith("a.example")
  })

  it("shows a saved-case match, the timeline, and a weak expand last", () => {
    const onFocus = vi.fn()
    render(
      <CampaignPanel
        saved={false}
        suggestions={[
          { entity_id: "rare", label: "Kit structure", rel_type: "matches_kit", reason: "Rare artifact shared with a saved case.", weak: false },
          { entity_id: "ns", label: "ns1.cloudflare.com", rel_type: "uses_nameserver", reason: "A public DNS provider is non-discriminating without further evidence.", weak: true },
        ]}
        campaign={{
          active: true,
          matches: [
            {
              artifact_kind: "kit",
              artifact_label: "Kit structure abcd1234",
              saved_investigation_id: "saved-1",
              saved_title: "kit-one.example",
              saved_indicator: "kit-one.example",
              entity_id: "dom-1",
              observation_ids: ["obs-1"],
            },
          ],
          case_count: 1,
          domain_count: 1,
          artifact_count: 1,
          withheld_common: 0,
          timeline: [{ kind: "registration", at: "2024-03-01", label: "Registration date published", subject: "kit-one.example" }],
          note: "Matches are rare artifacts shared with this analyst's saved cases. They do not assert malice and they do not name an operator.",
        }}
        onFocus={onFocus}
      />,
    )
    expect(screen.getByText(/Shares a rare artifact with 1 domain in 1 saved case/)).toBeInTheDocument()
    expect(screen.getByText("2024-03-01")).toBeInTheDocument()
    expect(screen.getByText(/Save this case to compare it with later searches/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Kit structure abcd1234/ }))
    expect(onFocus).toHaveBeenCalledWith("dom-1")
    const buttons = screen.getAllByRole("button")
    const rare = buttons.findIndex((button) => button.textContent?.includes("Kit structure"))
    const cloudflare = buttons.findIndex((button) => button.textContent?.includes("ns1.cloudflare.com"))
    expect(rare).toBeGreaterThan(-1)
    expect(cloudflare).toBeGreaterThan(rare)
  })
})
