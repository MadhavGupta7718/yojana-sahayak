"use client";

import { useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "sources", label: "Sources" },
  { id: "crawl-review", label: "Crawl review" },
  { id: "schemes", label: "Schemes" },
  { id: "partners", label: "Partners" },
  { id: "upload", label: "Manual upload" },
] as const;

function labelKey(key: string) {
  const labels: Record<string, string> = {
    total_schemes: "Active unique schemes",
    discontinued_schemes: "Discontinued / duplicates",
    undoable_changes: "Undoable changes",
    pending_changes: "Leftover pending changes",
    total_partners: "Active partners",
    government_sources: "Government sources",
    enabled_sources: "Enabled sources",
    successful_runs: "Successful runs",
    failed_runs: "Failed runs",
    stale_schemes: "Unverified schemes",
  };
  return labels[key] || key.replace(/_/g, " ");
}

function disabledReason(s: {
  enabled: boolean;
  notes?: string | null;
  discovery_status?: string;
  status?: string;
}) {
  if (s.enabled) return null;
  if (s.notes) return s.notes;
  if (s.discovery_status === "pending_review") {
    return "Pending admin review — not auto-enabled until relevance and authority are verified.";
  }
  if (s.status === "MANUAL/RESTRICTED") {
    return "Site blocks automated crawling (robots/HTTP). Use Manual upload for official documents.";
  }
  return "Disabled by design until an admin verifies robots.txt, relevance, and authority. Enable only when ready to crawl.";
}

const EMPTY_SOURCE_FORM = {
  source_name: "",
  organization: "",
  base_url: "https://",
  source_type: "institution",
  authority_level: 60,
  crawl_frequency: 60,
  enabled: false,
  notes: "",
};

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [overview, setOverview] = useState<any>(null);
  const [sources, setSources] = useState<any[]>([]);
  const [changes, setChanges] = useState<any[]>([]);
  const [unlinkedChanges, setUnlinkedChanges] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<any | null>(null);
  const [schemes, setSchemes] = useState<any[]>([]);
  const [partners, setPartners] = useState<any[]>([]);
  const [versions, setVersions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("overview");
  const [busy, setBusy] = useState(false);
  /** Per-source crawl button phase. Synced from latest_run while a crawl is active. */
  const [crawlBtn, setCrawlBtn] = useState<
    Record<number, "idle" | "checking" | "running" | "finished" | "blocked" | "error">
  >({});
  const [crawlNote, setCrawlNote] = useState<Record<number, string>>({});
  const [schedulePaused, setSchedulePaused] = useState(false);
  const [sourceForm, setSourceForm] = useState(EMPTY_SOURCE_FORM);
  const [addingSource, setAddingSource] = useState(false);

  const sourceNameById = useMemo(() => {
    const map: Record<number, string> = {};
    for (const s of sources) map[s.id] = s.source_name;
    return map;
  }, [sources]);

  const anyCrawlBusy = useMemo(
    () => Object.values(crawlBtn).some((p) => p === "checking" || p === "running"),
    [crawlBtn],
  );

  const changesByScheme = useMemo(() => {
    const groups: Record<string, { id: string; title: string; items: any[] }> = {};
    for (const c of changes) {
      const id = `${c.entity_type}:${c.entity_id ?? c.entity_key ?? c.id}`;
      if (!groups[id]) {
        groups[id] = {
          id,
          title: c.entity_name || c.entity_key || `${c.entity_type} #${c.entity_id || "?"}`,
          items: [],
        };
      }
      groups[id].items.push(c);
    }
    return Object.values(groups);
  }, [changes]);

  const unlinkedByScheme = useMemo(() => {
    const groups: Record<string, { id: string; title: string; items: any[] }> = {};
    for (const c of unlinkedChanges) {
      const id = `${c.entity_type}:${c.entity_id ?? c.entity_key ?? c.id}`;
      if (!groups[id]) {
        groups[id] = {
          id,
          title: c.entity_name || c.entity_key || `${c.entity_type} #${c.entity_id || "?"}`,
          items: [],
        };
      }
      groups[id].items.push(c);
    }
    return Object.values(groups);
  }, [unlinkedChanges]);

  function formatChangeValue(value: unknown) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "string") return value || "—";
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  function setSourceCrawl(
    id: number,
    phase: "idle" | "checking" | "running" | "finished" | "blocked" | "error",
    note?: string,
  ) {
    setCrawlBtn((prev) => ({ ...prev, [id]: phase }));
    if (note !== undefined) setCrawlNote((prev) => ({ ...prev, [id]: note }));
  }

  function formatRunSummary(run: any | null | undefined): string {
    if (!run) return "";
    return (
      `Run #${run.id}: ${run.status}` +
      ` · pages ${run.pages_crawled ?? 0}` +
      ` · docs ${run.documents_processed ?? 0}` +
      ` · changes ${run.changes_detected ?? 0}` +
      ` · errors ${run.error_count ?? 0}`
    );
  }

  function syncCrawlButtonsFromSources(sourceList: any[]) {
    setCrawlBtn((prev) => {
      const next = { ...prev };
      for (const s of sourceList) {
        const run = s.latest_run;
        if (!run) continue;
        const local = next[s.id];
        if (run.status === "queued" || run.status === "running") {
          next[s.id] = "running";
        } else if (local === "running" || local === "checking") {
          if (run.status === "success") next[s.id] = "finished";
          else if (run.status === "restricted") next[s.id] = "blocked";
          else next[s.id] = "error";
        }
      }
      return next;
    });
    setCrawlNote((prev) => {
      const next = { ...prev };
      for (const s of sourceList) {
        const run = s.latest_run;
        if (!run) continue;
        const local = prev[s.id];
        if (run.status === "queued" || run.status === "running") {
          next[s.id] = formatRunSummary(run) + (run.status === "queued" ? " — waiting for scraper…" : " — crawling…");
        } else if (local || run.end_time) {
          const prevNote = (prev[s.id] || "").toLowerCase();
          if (
            prevNote.includes("run #") ||
            prevNote.includes("queued") ||
            prevNote.includes("crawling") ||
            prevNote.includes("checking")
          ) {
            next[s.id] = formatRunSummary(run);
          }
        }
      }
      return next;
    });
  }

  function crawlabilityLine(ability: any | null | undefined): string {
    if (!ability) return "";
    const robots =
      ability.robots_allowed === true
        ? "robots allowed"
        : ability.robots_allowed === false
          ? "robots disallowed"
          : "robots unknown";
    const http = ability.http_ok
      ? `homepage OK${ability.http_status != null ? ` (${ability.http_status})` : ""}`
      : "homepage not reachable";
    const verdict =
      ability.verdict === "allowed"
        ? "Can crawl"
        : ability.verdict === "blocked"
          ? "Restricted"
          : "Uncertain";
    return `${verdict} · ${robots} · ${http}${ability.summary ? ` — ${ability.summary}` : ""}`;
  }

  async function adminFetch(path: string, options?: RequestInit) {
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options?.headers || {}),
      },
    });
    if (!res.ok) {
      const text = await res.text();
      let message = text;
      try {
        const parsed = JSON.parse(text);
        if (typeof parsed?.detail === "string") message = parsed.detail;
        else if (Array.isArray(parsed?.detail)) message = parsed.detail.map((d: any) => d.msg || JSON.stringify(d)).join("; ");
      } catch {
        /* keep raw text */
      }
      throw new Error(message || `Request failed (${res.status})`);
    }
    return res.json();
  }

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const body = new URLSearchParams();
    body.set("username", username);
    body.set("password", password);
    const res = await fetch(`${API_URL}/api/v1/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      setError("Login failed. Check username and password.");
      return;
    }
    const data = await res.json();
    setToken(data.access_token);
  }

  async function refresh() {
    if (!token) return;
    setBusy(true);
    try {
      const [o, s, u, r, sch, p, ctrl] = await Promise.all([
        adminFetch("/api/v1/admin/overview"),
        adminFetch("/api/v1/admin/sources"),
        adminFetch("/api/v1/admin/changes?undoable=true&unlinked=true"),
        adminFetch("/api/v1/admin/runs"),
        adminFetch("/api/v1/admin/schemes"),
        adminFetch("/api/v1/admin/partners"),
        adminFetch("/api/v1/admin/crawls/control").catch(() => ({ schedule_paused: false })),
      ]);
      setOverview(o);
      setSources(s);
      setUnlinkedChanges(u);
      setRuns(r);
      setSchemes(sch);
      setPartners(p);
      setSchedulePaused(Boolean(ctrl?.schedule_paused));
      syncCrawlButtonsFromSources(s);
      if (selectedRun?.id) {
        const [runDetail, runChanges] = await Promise.all([
          adminFetch(`/api/v1/admin/runs/${selectedRun.id}`),
          adminFetch(`/api/v1/admin/changes?run_id=${selectedRun.id}`),
        ]);
        setSelectedRun(runDetail);
        setChanges(runChanges);
      } else {
        setChanges([]);
      }
      setError(null);
      return { runs: r as any[], sources: s as any[] };
    } catch (err: any) {
      setError(err.message || "Failed to load admin data");
      return null;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (token) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // While a crawl is queued/running, poll so Sources status and buttons stay truthful
  useEffect(() => {
    if (!token || !anyCrawlBusy) return;
    const id = window.setInterval(() => {
      refresh();
    }, 4000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, anyCrawlBusy]);

  async function openRun(run: any) {
    setError(null);
    setBusy(true);
    try {
      const [runDetail, runChanges] = await Promise.all([
        adminFetch(`/api/v1/admin/runs/${run.id}`),
        adminFetch(`/api/v1/admin/changes?run_id=${run.id}`),
      ]);
      setSelectedRun(runDetail);
      setChanges(runChanges);
    } catch (err: any) {
      setError(err.message || "Could not load crawl changes");
    } finally {
      setBusy(false);
    }
  }

  function backToRuns() {
    setSelectedRun(null);
    setChanges([]);
  }

  async function undoChange(id: number) {
    setError(null);
    setNotice(null);
    if (!window.confirm("Undo this field change and restore the previous value?")) {
      return;
    }
    try {
      const out = await adminFetch(`/api/v1/admin/changes/${id}/undo`, { method: "POST" });
      setNotice(out.message || "Change undone.");
      await refresh();
    } catch (err: any) {
      setError(err.message || "Could not undo change");
    }
  }

  function renderChangeGroups(groups: { id: string; title: string; items: any[] }[]) {
    if (!groups.length) return <p className="panel">No field changes in this view.</p>;
    return groups.map((group) => (
      <div key={group.id} className="admin-row">
        <div className="font-semibold" style={{ marginBottom: "0.75rem" }}>
          {group.title}
        </div>
        <div className="stack" style={{ gap: "0.85rem" }}>
          {group.items.map((c) => (
            <div key={c.id} style={{ borderTop: "1px solid var(--border, #e5e7eb)", paddingTop: "0.75rem" }}>
              <div className="admin-row__top" style={{ alignItems: "flex-start" }}>
                <div>
                  <div className="font-semibold">
                    {c.field_name}{" "}
                    <span className="admin-badge muted">{c.status}</span>
                    {c.is_sensitive ? <span className="admin-badge warn">Sensitive</span> : null}
                  </div>
                  <div className="admin-meta">
                    Old: {formatChangeValue(c.old_value)} → New: {formatChangeValue(c.new_value)}
                  </div>
                  <div className="admin-meta">Applied {c.detected_at || "—"}</div>
                  {c.source_url && (
                    <a className="source-link" href={c.source_url} target="_blank" rel="noreferrer">
                      Official source
                    </a>
                  )}
                </div>
                {c.can_undo ? (
                  <button className="btn btn-secondary" type="button" onClick={() => undoChange(c.id)}>
                    Undo
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    ));
  }

  async function purgeNonSchemes() {
    setError(null);
    setNotice(null);
    if (
      !window.confirm(
        "Hide all non-scheme pages (privacy/FAQ/terms/etc.) from citizen listings? They will be marked discontinued.",
      )
    ) {
      return;
    }
    try {
      const out = await adminFetch("/api/v1/admin/schemes/purge-non-schemes", { method: "POST" });
      setNotice(out.message || `Removed ${out.removed || 0} non-scheme row(s).`);
      refresh();
    } catch (err: any) {
      setError(err.message || "Could not purge non-schemes");
    }
  }

  async function clearStuckCrawls() {
    setError(null);
    setNotice(null);
    try {
      const out = await adminFetch("/api/v1/admin/crawls/clear-stuck", { method: "POST" });
      setCrawlBtn({});
      setCrawlNote({});
      setSchedulePaused(false);
      setNotice(
        out.cleared
          ? `Cleared ${out.cleared} stuck crawl(s). Schedule resumed. You can start a new crawl now.`
          : "No stuck crawls found. Schedule resumed.",
      );
      refresh();
    } catch (err: any) {
      setError(err.message || "Could not clear stuck crawls");
    }
  }

  async function resumeSchedule() {
    setError(null);
    setNotice(null);
    try {
      const out = await adminFetch("/api/v1/admin/crawls/resume-schedule", { method: "POST" });
      setSchedulePaused(false);
      setNotice(out.message || "Schedule resumed.");
      refresh();
    } catch (err: any) {
      setError(err.message || "Could not resume schedule");
    }
  }

  async function crawlExclusive(id: number) {
    setError(null);
    setNotice(null);
    setTab("sources");
    setSourceCrawl(id, "checking", "Pausing other crawls and checking site…");
    try {
      const out = await adminFetch(`/api/v1/admin/sources/${id}/crawl-exclusive`, { method: "POST" });
      const checkLine = crawlabilityLine(out.crawlability);
      if (out.started === false && out.status === "blocked") {
        setSourceCrawl(id, "blocked", checkLine || out.message || "Crawl blocked.");
        return;
      }
      setSchedulePaused(true);
      const runHint = out.run_id ? ` Run #${out.run_id}.` : "";
      setSourceCrawl(
        id,
        "running",
        `${checkLine || "OK."} ${out.message || "Exclusive crawl queued."}${runHint}`,
      );
      setNotice(out.message || "Exclusive crawl started. Schedule is paused.");
      refresh();
    } catch (err: any) {
      const msg = err?.message || "Failed to start exclusive crawl";
      setSourceCrawl(id, "error", msg);
      setError(msg);
    }
  }

  async function crawl(id: number) {
    setError(null);
    setNotice(null);
    setTab("sources");
    setSourceCrawl(id, "checking", "Checking robots + homepage…");
    try {
      const out = await adminFetch(`/api/v1/admin/sources/${id}/crawl`, { method: "POST" });
      const checkLine = crawlabilityLine(out.crawlability);

      if (out.started === false && out.status === "blocked") {
        setSourceCrawl(
          id,
          "blocked",
          checkLine || out.message || "Crawl blocked by website restrictions.",
        );
        return;
      }

      if (out.started === false && (out.status === "running" || out.status === "queued")) {
        setSourceCrawl(id, "idle", out.message || "Another crawl is already in progress.");
        setNotice(out.message || "Another crawl is already in progress.");
        refresh();
        return;
      }

      // Accepted into queue — poll will flip to finished/error when the run ends.
      const runHint = out.run_id ? ` Run #${out.run_id}.` : "";
      setSourceCrawl(
        id,
        "running",
        `${checkLine || "OK."} ${out.message || "Crawl queued."}${runHint}`,
      );
      refresh();
    } catch (err: any) {
      const msg = err?.message || "Failed to check/start crawl";
      setSourceCrawl(id, "error", msg);
      setError(msg);
    }
  }

  async function checkCrawlOnly(id: number) {
    setError(null);
    setNotice(null);
    setTab("sources");
    setSourceCrawl(id, "checking", "Checking robots + homepage…");
    try {
      const check = await adminFetch(`/api/v1/admin/sources/${id}/crawl-check`, { method: "POST" });
      const ability = check.crawlability;
      const line = crawlabilityLine(ability) || ability?.summary || "Check finished.";
      // Keep Crawl button idle; only show check result under the row.
      setSourceCrawl(id, ability?.verdict === "blocked" ? "blocked" : "idle", line);
    } catch (err: any) {
      const msg = err?.message || "Crawlability check failed";
      setSourceCrawl(id, "error", msg);
      setError(msg);
    }
  }

  async function toggleSource(id: number, enabled: boolean) {
    await adminFetch(`/api/v1/admin/sources/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    refresh();
  }

  async function addSource(e: React.FormEvent) {
    e.preventDefault();
    setAddingSource(true);
    setError(null);
    try {
      await adminFetch("/api/v1/admin/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_name: sourceForm.source_name.trim(),
          organization: sourceForm.organization.trim(),
          base_url: sourceForm.base_url.trim(),
          source_type: sourceForm.source_type,
          authority_level: Number(sourceForm.authority_level) || 50,
          crawl_frequency: Number(sourceForm.crawl_frequency) || 60,
          enabled: Boolean(sourceForm.enabled),
          notes: sourceForm.notes.trim() || "Added from admin dashboard",
        }),
      });
      setSourceForm(EMPTY_SOURCE_FORM);
      await refresh();
      setTab("sources");
    } catch (err: any) {
      setError(err.message || "Could not add source");
    } finally {
      setAddingSource(false);
    }
  }

  async function loadVersions(schemeId: number) {
    const v = await adminFetch(`/api/v1/admin/schemes/${schemeId}/versions`);
    setVersions(v);
  }

  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const res = await fetch(`${API_URL}/api/v1/admin/uploads`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    form.reset();
    refresh();
  }

  if (!token) {
    return (
      <div className="page-wrap" style={{ maxWidth: "28rem" }}>
        <h1 className="text-navy font-display">Admin Login</h1>
        <p className="mt-2 text-sm text-muted">
          Default local credentials (from .env): username <strong>admin</strong>, password{" "}
          <strong>Admin@ChangeMe123</strong>. Change these before any public deployment.
        </p>
        <form onSubmit={login} className="panel mt-6 stack">
          <div>
            <label className="label">Username</label>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="error-box">{error}</p>}
          <button className="btn btn-primary w-full" type="submit">
            Sign in
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="admin-shell">
      <div className="admin-header">
        <div>
          <h1>Admin Dashboard</h1>
          <p className="text-sm text-muted mt-2" style={{ marginBottom: 0 }}>
            Manage official sources, review data changes, schemes, and channel partners.
          </p>
        </div>
        <div className="admin-actions">
          <button className="btn btn-secondary" type="button" onClick={() => refresh()} disabled={busy}>
            {busy ? "Refreshing…" : "Refresh data"}
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => {
              setToken("");
              setVersions([]);
              setCrawlBtn({});
              setCrawlNote({});
            }}
          >
            Sign out
          </button>
        </div>
      </div>

      {error && <p className="error-box">{error}</p>}
      {notice && <p className="admin-crawl-result">{notice}</p>}

      <nav className="admin-tabs" aria-label="Admin sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-tab ${tab === t.id ? "is-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "overview" && overview && (
        <div className="admin-stat-grid">
          {Object.entries(overview).map(([k, v]) => (
            <div key={k} className="admin-stat">
              <div className="admin-stat__label">{labelKey(k)}</div>
              <div className="admin-stat__value">{String(v)}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "sources" && (
        <div className="admin-list">
          <div className="admin-callout">
            <strong>Why some websites are disabled</strong>
            <p>
              Verified sources stay enabled for crawling (NSFDC by default). Other seeded portals start{" "}
              <strong>disabled</strong> until an admin checks robots.txt, relevance, and authority. You can also
              register any additional website URL below — leave it disabled until reviewed. Existing government
              sources and scraped schemes are kept; new sources are additive.
            </p>
            <div className="admin-actions mt-3">
              <button className="btn btn-secondary" type="button" onClick={() => clearStuckCrawls()}>
                Clear stuck crawls
              </button>
              {schedulePaused && (
                <button className="btn btn-primary" type="button" onClick={() => resumeSchedule()}>
                  Resume schedule
                </button>
              )}
            </div>
            {schedulePaused && (
              <p className="admin-meta" style={{ marginTop: "0.75rem", marginBottom: 0 }}>
                Scheduled crawls are paused (exclusive mode). Other crawls were cancelled. Click{" "}
                <strong>Resume schedule</strong> when you want periodic crawls again.
              </p>
            )}
          </div>

          <form className="admin-row admin-add-source" onSubmit={addSource}>
            <h3 className="font-semibold" style={{ margin: "0 0 0.75rem" }}>
              Add website to crawl
            </h3>
            <p className="admin-meta" style={{ marginTop: 0, marginBottom: "0.85rem" }}>
              Register any website URL to crawl (government or other published scheme portals). Leave “Enable for
              crawl” off until you have verified it.
            </p>
            <div className="admin-form-grid">
              <div>
                <label className="label">Source name *</label>
                <input
                  className="input"
                  required
                  value={sourceForm.source_name}
                  onChange={(e) => setSourceForm((f) => ({ ...f, source_name: e.target.value }))}
                  placeholder="e.g. UP SCA / NSFDC FAQs"
                />
              </div>
              <div>
                <label className="label">Organization *</label>
                <input
                  className="input"
                  required
                  value={sourceForm.organization}
                  onChange={(e) => setSourceForm((f) => ({ ...f, organization: e.target.value }))}
                  placeholder="Official organization name"
                />
              </div>
              <div className="admin-form-span">
                <label className="label">Base URL *</label>
                <input
                  className="input"
                  required
                  type="url"
                  value={sourceForm.base_url}
                  onChange={(e) => setSourceForm((f) => ({ ...f, base_url: e.target.value }))}
                  placeholder="https://example.org/schemes/"
                />
              </div>
              <div>
                <label className="label">Source type</label>
                <select
                  className="select"
                  value={sourceForm.source_type}
                  onChange={(e) => setSourceForm((f) => ({ ...f, source_type: e.target.value }))}
                >
                  <option value="institution">Institution</option>
                  <option value="ministry">Ministry</option>
                  <option value="state">State / SCA</option>
                  <option value="central">Central</option>
                  <option value="open_data">Open data</option>
                </select>
              </div>
              <div>
                <label className="label">Authority (0–100)</label>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={100}
                  value={sourceForm.authority_level}
                  onChange={(e) => setSourceForm((f) => ({ ...f, authority_level: Number(e.target.value) }))}
                />
              </div>
              <div>
                <label className="label">Crawl every (minutes)</label>
                <input
                  className="input"
                  type="number"
                  min={5}
                  value={sourceForm.crawl_frequency}
                  onChange={(e) => setSourceForm((f) => ({ ...f, crawl_frequency: Number(e.target.value) }))}
                />
              </div>
              <div className="admin-form-span">
                <label className="label">Notes</label>
                <input
                  className="input"
                  value={sourceForm.notes}
                  onChange={(e) => setSourceForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="Why this source is trusted / any crawl limits"
                />
              </div>
            </div>
            <label className="admin-check">
              <input
                type="checkbox"
                checked={sourceForm.enabled}
                onChange={(e) => setSourceForm((f) => ({ ...f, enabled: e.target.checked }))}
              />
              Enable for crawl immediately
            </label>
            <div className="admin-actions mt-3">
              <button className="btn btn-primary" type="submit" disabled={addingSource}>
                {addingSource ? "Adding…" : "Add source"}
              </button>
            </div>
          </form>

          {sources.length === 0 && <p className="panel">No sources registered yet.</p>}
          {sources.map((s) => {
            const reason = disabledReason(s);
            const phase = crawlBtn[s.id] || "idle";
            const note = crawlNote[s.id];
            const latest = s.latest_run;
            const busyHere = phase === "checking" || phase === "running";
            const crawlLabel =
              phase === "checking"
                ? "Checking…"
                : phase === "running"
                  ? "Running…"
                  : phase === "finished"
                    ? "Finished"
                    : phase === "blocked"
                      ? "Blocked"
                      : phase === "error"
                        ? "Failed"
                        : "Crawl now";
            const robotsLabel =
              s.robots_allowed === true ? "allowed" : s.robots_allowed === false ? "disallowed" : "unknown";
            return (
              <div key={s.id} className={`admin-row ${busyHere ? "admin-row--crawling" : ""}`}>
                <div className="admin-row__top">
                  <div>
                    <div className="font-semibold">{s.source_name}</div>
                    <div className="admin-meta">
                      <span className={`admin-badge ${s.enabled ? "" : "muted"}`}>
                        {s.enabled ? "Enabled" : "Disabled"}
                      </span>{" "}
                      <span className="admin-badge muted">{s.status || "PENDING"}</span>{" "}
                      <span className="admin-badge muted">{s.discovery_status || "approved"}</span>
                      {" · "}robots: {robotsLabel}
                      {" · "}last crawl:{" "}
                      {s.last_successful_crawl
                        ? new Date(s.last_successful_crawl).toLocaleString()
                        : "—"}
                    </div>
                    {latest && (
                      <div className="admin-meta" style={{ marginTop: 4 }}>
                        Latest run: {formatRunSummary(latest)}
                        {latest.end_time
                          ? ` · ended ${new Date(latest.end_time).toLocaleString()}`
                          : latest.status === "queued" || latest.status === "running"
                            ? " · in progress"
                            : ""}
                      </div>
                    )}
                    <a className="source-link" href={s.base_url} target="_blank" rel="noreferrer">
                      {s.base_url}
                    </a>
                    {reason && (
                      <p className="admin-disabled-reason">
                        <strong>Why disabled:</strong> {reason}
                      </p>
                    )}
                    {note && (
                      <p className="admin-crawl-result" role="status">
                        {note}
                      </p>
                    )}
                  </div>
                  <div className="admin-actions">
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => toggleSource(s.id, !s.enabled)}
                      disabled={anyCrawlBusy}
                      title={anyCrawlBusy ? "Wait for the current crawl action to finish" : undefined}
                    >
                      {s.enabled ? "Disable" : "Enable"}
                    </button>
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => checkCrawlOnly(s.id)}
                      disabled={anyCrawlBusy}
                      title="Check robots.txt and homepage without starting a full crawl"
                    >
                      {phase === "checking" ? "Checking…" : "Check if crawlable"}
                    </button>
                    <button
                      className="btn btn-primary"
                      type="button"
                      onClick={() => crawl(s.id)}
                      disabled={!s.enabled || anyCrawlBusy}
                      title={
                        !s.enabled
                          ? "Enable this source first"
                          : anyCrawlBusy
                            ? "Another crawl action is in progress"
                            : "Check crawlability, then queue crawl"
                      }
                    >
                      {crawlLabel}
                    </button>
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => crawlExclusive(s.id)}
                      disabled={!s.enabled || anyCrawlBusy}
                      title={
                        !s.enabled
                          ? "Enable this source first"
                          : "Cancel other crawls, pause schedule, and crawl only this source now"
                      }
                    >
                      Pause others & crawl
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === "crawl-review" && (
        <div className="admin-list">
          {selectedRun ? (
            <>
              <div className="admin-row admin-row__top" style={{ alignItems: "center" }}>
                <div>
                  <div className="font-semibold">
                    Run #{selectedRun.id} · {selectedRun.source_name || sourceNameById[selectedRun.source_id] || `Source ${selectedRun.source_id}`}
                  </div>
                  <p className="admin-meta" style={{ margin: "0.35rem 0 0" }}>
                    {selectedRun.organization ? `${selectedRun.organization} · ` : ""}
                    {selectedRun.status} · pages {selectedRun.pages_crawled} · docs{" "}
                    {selectedRun.documents_processed} · changes {selectedRun.changes_detected}
                    {typeof selectedRun.linked_changes === "number"
                      ? ` (${selectedRun.linked_changes} linked)`
                      : ""}{" "}
                    · errors {selectedRun.error_count}
                  </p>
                  <p className="admin-meta" style={{ margin: "0.25rem 0 0" }}>
                    {selectedRun.start_time} → {selectedRun.end_time || "running…"}
                    {selectedRun.notes ? ` · ${selectedRun.notes}` : ""}
                  </p>
                </div>
                <div className="admin-actions">
                  <button className="btn btn-secondary" type="button" onClick={() => backToRuns()}>
                    Back to crawls
                  </button>
                </div>
              </div>
              <div className="admin-row">
                <div className="font-semibold">Changes in this crawl ({changes.length})</div>
                <p className="admin-meta" style={{ margin: "0.35rem 0 0" }}>
                  Field updates from this run. Undo restores one field at a time.
                </p>
              </div>
              {renderChangeGroups(changesByScheme)}
            </>
          ) : (
            <>
              <div className="admin-row admin-row__top" style={{ alignItems: "center" }}>
                <div>
                  <div className="font-semibold">Crawl review</div>
                  <p className="admin-meta" style={{ margin: "0.35rem 0 0" }}>
                    Open a crawl to see what changed, then undo individual fields if needed.
                  </p>
                </div>
              </div>
              {runs.length === 0 && <p className="panel">No crawl runs yet.</p>}
              {runs.map((r) => {
                const live = (r.status === "running" || r.status === "queued") && !r.end_time;
                const site =
                  r.source_name || sourceNameById[r.source_id] || `Source ${r.source_id || "?"}`;
                return (
                  <button
                    key={r.id}
                    type="button"
                    className={`admin-row ${live ? "admin-row--crawling" : ""}`}
                    onClick={() => openRun(r)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      cursor: "pointer",
                      appearance: "none",
                      font: "inherit",
                      color: "inherit",
                    }}
                  >
                    <div className="admin-row__top">
                      <div className="font-semibold">
                        Run #{r.id}
                        {live && <span className="admin-crawl-pulse"> Live</span>}
                      </div>
                      <span
                        className={`admin-badge ${r.status === "success" || r.status === "completed" ? "" : "warn"}`}
                      >
                        {r.status}
                      </span>
                    </div>
                    <div className="admin-meta">
                      {site}
                      {r.organization ? ` · ${r.organization}` : ""}
                    </div>
                    <div className="admin-meta">
                      pages {r.pages_crawled} · docs {r.documents_processed} · changes{" "}
                      {r.changes_detected}
                      {typeof r.linked_changes === "number" ? ` (${r.linked_changes} linked)` : ""} ·
                      errors {r.error_count}
                    </div>
                    <div className="admin-meta">
                      {r.start_time} → {r.end_time || "running…"}
                      {r.notes ? ` · ${r.notes}` : ""}
                    </div>
                    {live && (
                      <div className="admin-crawl-track admin-crawl-track--inline" aria-hidden>
                        <span className="admin-crawl-bar" />
                      </div>
                    )}
                  </button>
                );
              })}

              <div className="admin-row" style={{ marginTop: "1rem" }}>
                <div className="font-semibold">
                  Older / unlinked changes ({unlinkedChanges.length})
                </div>
                <p className="admin-meta" style={{ margin: "0.35rem 0 0" }}>
                  Changes recorded before crawl IDs were linked. You can still undo fields here.
                </p>
              </div>
              {renderChangeGroups(unlinkedByScheme)}
            </>
          )}
        </div>
      )}

      {tab === "schemes" && (
        <div className="admin-list">
          <div className="admin-row admin-row__top" style={{ alignItems: "center" }}>
            <div>
              <div className="font-semibold">Active unique schemes ({schemes.length})</div>
              <p className="admin-meta" style={{ margin: "0.35rem 0 0" }}>
                Same set as Explore/Find. Discontinued and title-variant duplicates are hidden here.
                Remove privacy/FAQ/terms pages that were wrongly saved as schemes.
              </p>
            </div>
            <div className="admin-actions">
              <button className="btn btn-secondary" type="button" onClick={() => purgeNonSchemes()}>
                Hide non-schemes
              </button>
            </div>
          </div>
          {schemes.length === 0 && <p className="panel">No schemes in database.</p>}
          {schemes.map((s) => (
            <div key={s.id} className="admin-row">
              <div className="admin-row__top">
                <div>
                  <div className="font-semibold">{s.name}</div>
                  <div className="admin-meta">
                    v{s.current_version} · {s.status} · verified {s.last_verified || "—"}
                    {s.purpose ? ` · ${s.purpose}` : ""}
                  </div>
                </div>
                <button className="btn btn-secondary" type="button" onClick={() => loadVersions(s.id)}>
                  View versions
                </button>
              </div>
            </div>
          ))}
          {versions.length > 0 && (
            <div className="admin-row">
              <h3 className="font-semibold" style={{ margin: 0 }}>
                Version history
              </h3>
              {versions.map((v) => (
                <pre key={v.id} className="admin-pre">
                  v{v.version_number}: {JSON.stringify(v.data_snapshot, null, 2)}
                </pre>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "partners" && (
        <div className="admin-list">
          {partners.length === 0 && <p className="panel">No partners ingested yet.</p>}
          {partners.map((p) => (
            <div key={p.id} className="admin-row">
              <div className="font-semibold">{p.name}</div>
              <div className="admin-meta">
                {[p.district, p.state].filter(Boolean).join(", ") || "Region not published"} · {p.status} ·{" "}
                {p.last_verified || "unverified"}
                {p.latitude != null && p.longitude != null ? " · has map coordinates" : " · no coordinates"}
              </div>
              {p.source_url && (
                <a className="source-link" href={p.source_url} target="_blank" rel="noreferrer">
                  Official source
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "upload" && (
        <form className="panel mt-6 stack" onSubmit={upload}>
          <p className="text-sm text-muted" style={{ margin: 0 }}>
            For MANUAL/RESTRICTED sources: upload an official PDF/HTML document. This does not bypass site
            restrictions.
          </p>
          <div>
            <label className="label">Source ID</label>
            <input className="input" name="source_id" required />
          </div>
          <div>
            <label className="label">Optional official URL</label>
            <input className="input" name="source_url" />
          </div>
          <div>
            <label className="label">File</label>
            <input className="input" type="file" name="file" required />
          </div>
          <button className="btn btn-primary" type="submit">
            Ingest upload
          </button>
        </form>
      )}
    </div>
  );
}
