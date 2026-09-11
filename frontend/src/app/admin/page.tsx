"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

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
  const [tab, setTab] = useState("overview");

  async function adminFetch(path: string, options?: RequestInit) {
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options?.headers || {}),
      },
    });
    if (!res.ok) throw new Error(await res.text());
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
      setError("Login failed");
      return;
    }
    const data = await res.json();
    setToken(data.access_token);
  }

  async function refresh() {
    if (!token) return;
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
    } catch (err: any) {
      setError(err.message || "Failed to load admin data");
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

  async function crawl(id: number) {
    await adminFetch(`/api/v1/admin/sources/${id}/crawl`, { method: "POST" });
    refresh();
  }

  async function toggleSource(id: number, enabled: boolean) {
    await adminFetch(`/api/v1/admin/sources/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    refresh();
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
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-3xl text-[var(--navy)]">Admin Dashboard</h1>
        <button className="btn btn-secondary" type="button" onClick={refresh}>
          Refresh
        </button>
      </div>
      {error && <p className="mt-3 text-red-600">{error}</p>}

      <div className="mt-6 flex flex-wrap gap-2">
        {["overview", "sources", "changes", "runs", "schemes", "partners", "upload"].map((t) => (
          <button
            key={t}
            type="button"
            className={`btn ${tab === t ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "overview" && overview && (
        <div className="mt-6 grid gap-4 md:grid-cols-4">
          {Object.entries(overview).map(([k, v]) => (
            <div key={k} className="panel">
              <div className="text-sm text-[var(--muted)]">{k}</div>
              <div className="text-2xl font-bold text-[var(--navy)]">{String(v)}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "sources" && (
        <div className="mt-6 space-y-3">
          {sources.map((s) => (
            <div key={s.id} className="panel">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-semibold">{s.source_name}</div>
                  <div className="text-sm text-[var(--muted)]">
                    {s.status} · last crawl: {s.last_successful_crawl || "—"} · robots: {String(s.robots_allowed)}
                  </div>
                  <a className="text-sm underline" href={s.base_url} target="_blank" rel="noreferrer">
                    {s.base_url}
                  </a>
                </div>
                <div className="flex gap-2">
                  <button className="btn btn-secondary" type="button" onClick={() => toggleSource(s.id, !s.enabled)}>
                    {s.enabled ? "Disable" : "Enable"}
                  </button>
                  <button className="btn btn-primary" type="button" onClick={() => crawl(s.id)} disabled={!s.enabled}>
                    Crawl now
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "changes" && (
        <div className="mt-6 space-y-3">
          {changes.length === 0 && <p className="panel">No pending changes</p>}
          {changes.map((c) => (
            <div key={c.id} className="panel">
              <div className="font-semibold">
                {c.entity_type} / {c.field_name} {c.is_conflict ? "Conflict" : ""}
              </div>
              <div className="mt-1 text-sm">
                Old: {JSON.stringify(c.old_value)} → New: {JSON.stringify(c.new_value)}
              </div>
              {c.source_url && (
                <a className="text-sm underline" href={c.source_url} target="_blank" rel="noreferrer">
                  View source
                </a>
              )}
              <div className="mt-3 flex gap-2">
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
        <div className="mt-6 space-y-3">
          {runs.map((r) => (
            <div key={r.id} className="panel text-sm">
              #{r.id} source={r.source_id} status={r.status} pages={r.pages_crawled} docs={r.documents_processed}{" "}
              changes={r.changes_detected} errors={r.error_count}
              <div className="text-[var(--muted)]">
                {r.start_time} → {r.end_time || "running"}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "schemes" && (
        <div className="mt-6 space-y-3">
          {schemes.map((s) => (
            <div key={s.id} className="panel">
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <div className="font-semibold">{s.name}</div>
                  <div className="text-sm text-[var(--muted)]">
                    v{s.current_version} · {s.status} · verified {s.last_verified || "—"}
                  </div>
                </div>
                <button className="btn btn-secondary" type="button" onClick={() => loadVersions(s.id)}>
                  Versions
                </button>
              </div>
            </div>
          ))}
          {versions.length > 0 && (
            <div className="panel">
              <h3 className="font-semibold">Version history</h3>
              {versions.map((v) => (
                <pre key={v.id} className="mt-2 overflow-auto rounded bg-slate-50 p-2 text-xs">
                  v{v.version_number}: {JSON.stringify(v.data_snapshot, null, 2)}
                </pre>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "partners" && (
        <div className="mt-6 space-y-3">
          {partners.map((p) => (
            <div key={p.id} className="panel">
              <div className="font-semibold">{p.name}</div>
              <div className="text-sm text-[var(--muted)]">
                {p.district} {p.state} · {p.status} · {p.last_verified || "unverified"}
              </div>
              {p.source_url && (
                <a className="text-sm underline" href={p.source_url} target="_blank" rel="noreferrer">
                  Official source
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "upload" && (
        <form className="panel mt-6 space-y-3" onSubmit={upload}>
          <p className="text-sm text-[var(--muted)]">
            For MANUAL/RESTRICTED sources: upload an official PDF/HTML document. No bypass of site restrictions.
          </p>
          <label className="label">Source ID</label>
          <input className="input" name="source_id" required />
          <label className="label">Optional official URL</label>
          <input className="input" name="source_url" />
          <label className="label">File</label>
          <input className="input" type="file" name="file" required />
          <button className="btn btn-primary" type="submit">
            Ingest upload
          </button>
        </form>
      )}
    </div>
  );
}
