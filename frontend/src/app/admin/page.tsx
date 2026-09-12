"use client";

import { useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "sources", label: "Sources" },
  { id: "changes", label: "Change review" },
  { id: "runs", label: "Crawl runs" },
  { id: "schemes", label: "Schemes" },
  { id: "partners", label: "Partners" },
  { id: "upload", label: "Manual upload" },
] as const;

function labelKey(key: string) {
  return key.replace(/_/g, " ");
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
  const [runs, setRuns] = useState<any[]>([]);
  const [schemes, setSchemes] = useState<any[]>([]);
  const [partners, setPartners] = useState<any[]>([]);
  const [versions, setVersions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("overview");
  const [busy, setBusy] = useState(false);
  /** Per-source crawl button: idle → checking → running → finished (or blocked/error). No polling. */
  const [crawlBtn, setCrawlBtn] = useState<
    Record<number, "idle" | "checking" | "running" | "finished" | "blocked" | "error">
  >({});
  const [crawlNote, setCrawlNote] = useState<Record<number, string>>({});
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

  function setSourceCrawl(
    id: number,
    phase: "idle" | "checking" | "running" | "finished" | "blocked" | "error",
    note?: string,
  ) {
    setCrawlBtn((prev) => ({ ...prev, [id]: phase }));
    if (note !== undefined) setCrawlNote((prev) => ({ ...prev, [id]: note }));
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
      const [o, s, c, r, sch, p] = await Promise.all([
        adminFetch("/api/v1/admin/overview"),
        adminFetch("/api/v1/admin/sources"),
        adminFetch("/api/v1/admin/changes?status=pending_review"),
        adminFetch("/api/v1/admin/runs"),
        adminFetch("/api/v1/admin/schemes"),
        adminFetch("/api/v1/admin/partners"),
      ]);
      setOverview(o);
      setSources(s);
      setChanges(c);
      setRuns(r);
      setSchemes(sch);
      setPartners(p);
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

  async function decide(id: number, approve: boolean) {
    await adminFetch(`/api/v1/admin/changes/${id}/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve }),
    });
    refresh();
  }

  async function clearStuckCrawls() {
    setError(null);
    setNotice(null);
    try {
      const out = await adminFetch("/api/v1/admin/crawls/clear-stuck", { method: "POST" });
      setCrawlBtn({});
      setCrawlNote({});
      setNotice(
        out.cleared
          ? `Cleared ${out.cleared} stuck crawl(s). You can start a new crawl now.`
          : "No stuck crawls found.",
      );
    } catch (err: any) {
      setError(err.message || "Could not clear stuck crawls");
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
        setSourceCrawl(
          id,
          "running",
          `${checkLine || "OK."} ${out.message || "Another crawl is already in progress."}`,
        );
        return;
      }

      // Accepted into queue — keep button on Running until user sees result in Crawl runs.
      const runHint = out.run_id ? ` Run #${out.run_id}.` : "";
      setSourceCrawl(
        id,
        "running",
        `${checkLine || "OK."} ${out.message || "Crawl queued."}${runHint} Use Refresh data on Crawl runs.`,
      );
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
    const fd = new FormData(e.currentTarget);
    const res = await fetch(`${API_URL}/api/v1/admin/uploads`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    e.currentTarget.reset();
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
              Only <em>verified</em> government sources stay enabled for crawling (NSFDC by default). Others such as
              MoSJE, data.gov.in, or SCA placeholders start <strong>disabled</strong> until an admin checks robots.txt,
              relevance, and authority — this avoids scraping the wrong sites or blocked portals. Use{" "}
              <strong>Enable</strong> after review, or add a new official URL below.
            </p>
            <div className="admin-actions mt-3">
              <button className="btn btn-secondary" type="button" onClick={() => clearStuckCrawls()}>
                Clear stuck crawls
              </button>
            </div>
          </div>

          <form className="admin-row admin-add-source" onSubmit={addSource}>
            <h3 className="font-semibold" style={{ margin: "0 0 0.75rem" }}>
              Add website to crawl
            </h3>
            <p className="admin-meta" style={{ marginTop: 0, marginBottom: "0.85rem" }}>
              Register another official .gov / .nic.in source. Leave “Enable for crawl” off until you have verified it.
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
                  placeholder="https://example.gov.in/"
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
            return (
              <div key={s.id} className={`admin-row ${busyHere ? "admin-row--crawling" : ""}`}>
                <div className="admin-row__top">
                  <div>
                    <div className="font-semibold">{s.source_name}</div>
                    <div className="admin-meta">
                      <span className={`admin-badge ${s.enabled ? "" : "muted"}`}>
                        {s.enabled ? "Enabled" : "Disabled"}
                      </span>{" "}
                      <span className="admin-badge muted">{s.status}</span>{" "}
                      <span className="admin-badge muted">{s.discovery_status || "approved"}</span>
                      {" · "}last crawl: {s.last_successful_crawl || "—"}
                      {" · "}robots: {String(s.robots_allowed)}
                    </div>
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
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === "changes" && (
        <div className="admin-list">
          {changes.length === 0 && <p className="panel">No pending changes to review.</p>}
          {changes.map((c) => (
            <div key={c.id} className="admin-row">
              <div className="font-semibold">
                {c.entity_type} / {c.field_name}{" "}
                {c.is_conflict ? <span className="admin-badge warn">Conflict</span> : null}
              </div>
              <div className="admin-meta">
                Old: {JSON.stringify(c.old_value)} → New: {JSON.stringify(c.new_value)}
              </div>
              {c.source_url && (
                <a className="source-link" href={c.source_url} target="_blank" rel="noreferrer">
                  View source
                </a>
              )}
              <div className="admin-actions mt-3">
                <button className="btn btn-primary" type="button" onClick={() => decide(c.id, true)}>
                  Approve
                </button>
                <button className="btn btn-secondary" type="button" onClick={() => decide(c.id, false)}>
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "runs" && (
        <div className="admin-list">
          {runs.length === 0 && <p className="panel">No crawl runs yet.</p>}
          {runs.map((r) => {
            const live = (r.status === "running" || r.status === "queued") && !r.end_time;
            return (
              <div key={r.id} className={`admin-row ${live ? "admin-row--crawling" : ""}`}>
                <div className="admin-row__top">
                  <div className="font-semibold">
                    Run #{r.id}
                    {live && <span className="admin-crawl-pulse"> Live</span>}
                  </div>
                  <span className={`admin-badge ${r.status === "success" || r.status === "completed" ? "" : "warn"}`}>
                    {r.status}
                  </span>
                </div>
                <div className="admin-meta">
                  {sourceNameById[r.source_id] || `Source ${r.source_id}`} · pages {r.pages_crawled} · docs{" "}
                  {r.documents_processed} · changes {r.changes_detected} · errors {r.error_count}
                </div>
                <div className="admin-meta">
                  {r.start_time} → {r.end_time || "running…"}
                </div>
                {live && (
                  <div className="admin-crawl-track admin-crawl-track--inline" aria-hidden>
                    <span className="admin-crawl-bar" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {tab === "schemes" && (
        <div className="admin-list">
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
