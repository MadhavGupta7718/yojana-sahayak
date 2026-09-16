"use client";

import { useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";

type SchemeRow = {
  id: number;
  name: string;
  description?: string | null;
  max_loan?: number | null;
  interest_rate?: number | null;
  purpose?: string | null;
  scheme_type?: string | null;
  freshness?: string | null;
  source_url?: string | null;
  target_gender?: string | null;
  timeline?: { label?: string } | null;
};

export default function SchemesClient({
  initialSchemes,
  locale,
  labels,
}: {
  initialSchemes: SchemeRow[];
  locale: "en" | "hi";
  labels: {
    empty: string;
    notAvailable: string;
    freshness: string;
    officialSource: string;
    searchPlaceholder: string;
    showing: string;
    loadError: string;
    retry: string;
    maxLoan: string;
    interest: string;
    allPurposes: string;
  };
}) {
  const [schemes, setSchemes] = useState<SchemeRow[]>(initialSchemes || []);
  const [q, setQ] = useState("");
  const [purpose, setPurpose] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/schemes`, { cache: "no-store" });
      if (!res.ok) throw new Error(labels.loadError);
      const data = await res.json();
      setSchemes(Array.isArray(data) ? data : data.schemes || []);
    } catch {
      setError(labels.loadError);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Always refresh from API so Explore does not keep a stale SSR snapshot
    // after scrapes update scheme rows (or retire duplicates).
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const purposes = useMemo(() => {
    const set = new Set<string>();
    for (const s of schemes) {
      if (s.purpose) set.add(String(s.purpose));
    }
    return Array.from(set).sort();
  }, [schemes]);

  const filtered = useMemo(() => {
    const stop = new Set(["and", "or", "the", "a", "an", "of", "for", "to", "in", "on", "with"]);
    const rawTokens = q
      .trim()
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean);
    const tokens = rawTokens.filter((tok) => !stop.has(tok));
    const phrase = tokens.join(" ");
    const schemeNum = tokens.find((tok) => /^\d{1,3}$/.test(tok));

    const scored = schemes
      .filter((s) => {
        if (purpose && String(s.purpose || "").toLowerCase() !== purpose.toLowerCase()) return false;
        return true;
      })
      .map((s) => {
        const name = (s.name || "").toLowerCase();
        const desc = (s.description || "").toLowerCase();
        const blob = `${name} ${desc} ${s.scheme_type || ""} ${s.purpose || ""}`.toLowerCase();

        if (!tokens.length) return { s, score: 1 };

        // Scheme number in the query must appear in the title (avoids Scheme 07 on "… 08")
        if (schemeNum && !name.includes(schemeNum)) return { s, score: 0 };

        const nameHits = tokens.filter((tok) => name.includes(tok)).length;
        const blobHits = tokens.filter((tok) => blob.includes(tok)).length;
        if (nameHits < Math.min(2, tokens.length) && blobHits < tokens.length) return { s, score: 0 };

        let score = 0;
        if (name.includes(phrase)) score += 100;
        // Ignore gender words so "… Beauty … 08" still matches "… Men Beauty … 08"
        const compactName = name.replace(/\b(men|women|male|female)\b/g, " ").replace(/\s+/g, " ");
        if (compactName.includes(phrase)) score += 90;

        score += Math.round((nameHits / tokens.length) * 50);
        score += Math.round((blobHits / tokens.length) * 8);
        if (schemeNum && new RegExp(`scheme\\s*0*${Number(schemeNum)}\\b`).test(name)) score += 30;

        const activity = tokens.filter(
          (tok) => !/^\d+$/.test(tok) && !["scheme", "samajik", "nyay", "yojana", "loan"].includes(tok),
        );
        const activityInName = activity.filter((tok) => name.includes(tok)).length;
        if (activity.length) {
          if (activityInName === activity.length) score += 45;
          else if (activityInName === 0) score -= 40;
          else score += activityInName * 8;
        }

        // Require most query tokens to land in the title for a "best match"
        if (nameHits / tokens.length < 0.6) score -= 50;
        return { s, score };
      })
      .filter((row) => row.score >= 60)
      .sort((a, b) => b.score - a.score || (a.s.name || "").localeCompare(b.s.name || ""));

    if (!tokens.length) {
      return schemes.filter((s) => !purpose || String(s.purpose || "").toLowerCase() === purpose.toLowerCase());
    }
    if (!scored.length) return [];
    const best = scored[0].score;
    return scored.filter((row) => row.score >= best - 25).slice(0, 5).map((row) => row.s);
  }, [schemes, q, purpose]);

  return (
    <div className="ys-wrap ys-schemes">
      <div className="ys-schemes__toolbar">
        <input
          className="input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={labels.searchPlaceholder}
          aria-label={labels.searchPlaceholder}
        />
        <select className="select" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
          <option value="">{labels.allPurposes}</option>
          {purposes.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-secondary" onClick={reload} disabled={loading}>
          {labels.retry}
        </button>
      </div>

      <p className="ys-schemes__count">
        {labels.showing
          .replace("{shown}", String(filtered.length))
          .replace("{total}", String(schemes.length))}
      </p>

      {error && <p className="ys-empty">{error}</p>}
      {!error && schemes.length === 0 && <p className="ys-empty">{labels.empty}</p>}
      {!error && schemes.length > 0 && filtered.length === 0 && (
        <p className="ys-empty">{locale === "hi" ? "इस खोज से कोई योजना नहीं मिली।" : "No schemes match this search."}</p>
      )}

      {filtered.map((s) => (
        <article key={s.id} className="ys-scheme">
          <h2>{s.name}</h2>
          <p>{s.description?.slice(0, 280) || labels.notAvailable}</p>
          <div className="ys-scheme__meta">
            <span>
              {labels.maxLoan}:{" "}
              {s.max_loan != null ? `₹${Number(s.max_loan).toLocaleString("en-IN")}` : labels.notAvailable}
            </span>
            <span>
              {labels.interest}:{" "}
              {s.interest_rate != null ? `${s.interest_rate}%` : labels.notAvailable}
            </span>
            {s.purpose ? <span>{s.purpose}</span> : null}
            {s.timeline?.label ? <span>{s.timeline.label}</span> : null}
            <span>
              {labels.freshness}: {s.freshness || labels.notAvailable}
            </span>
          </div>
          {s.source_url && (
            <a className="ys-link" href={s.source_url} target="_blank" rel="noreferrer">
              {labels.officialSource} →
            </a>
          )}
        </article>
      ))}
    </div>
  );
}
