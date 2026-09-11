"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/api";

type Messages = Record<string, string>;

type Rec = {
  scheme_id: number;
  name: string;
  score: number;
  why: { status: string; text: string }[];
  interest_rate: number | null;
  max_loan: number | null;
  tenure: number | null;
  moratorium: number | null;
  required_documents: string[] | null;
  source_url: string | null;
  last_verified: string | null;
  freshness: string;
  disclaimer: string;
  citations: { field_name: string | null; source_url: string; source_title: string | null }[];
  unavailable_fields: string[];
};

const STEPS = ["profile", "finance", "project", "results"] as const;

export default function FindClient({ messages }: { messages: Messages }) {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nlpText, setNlpText] = useState("");
  const [recs, setRecs] = useState<Rec[]>([]);
  const [selected, setSelected] = useState<Rec | null>(null);
  const [emi, setEmi] = useState<any>(null);
  const [partners, setPartners] = useState<any>(null);
  const [locMode, setLocMode] = useState<"geo" | "manual">("manual");
  const [form, setForm] = useState({
    age: "",
    category: "SC",
    state: "",
    district: "",
    annual_family_income: "",
    existing_loan: "no",
    purpose: "business",
    project_type: "",
    project_cost: "",
    loan_required: "",
    education_status: "",
    address: "",
    city: "",
    pin_code: "",
    latitude: "" as string,
    longitude: "" as string,
  });

  const progress = ((step + 1) / STEPS.length) * 100;

  function update(key: string, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function parseNlp() {
    if (!nlpText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const out = await api<{ extracted: Record<string, unknown> }>("/api/v1/nlp/parse", {
        method: "POST",
        body: JSON.stringify({ text: nlpText }),
      });
      const e = out.extracted || {};
      setForm((f) => ({
        ...f,
        purpose: (e.purpose as string) || f.purpose,
        project_type: (e.project_type as string) || f.project_type,
        category: (e.category as string) || f.category,
        age: e.age != null ? String(e.age) : f.age,
        loan_required: e.loan_required != null ? String(e.loan_required) : f.loan_required,
        annual_family_income:
          e.annual_family_income != null ? String(e.annual_family_income) : f.annual_family_income,
      }));
    } catch {
      setError(messages.error);
    } finally {
      setLoading(false);
    }
  }

  async function runAssessment() {
    setLoading(true);
    setError(null);
    try {
      const body = {
        age: form.age ? Number(form.age) : null,
        category: form.category || null,
        state: form.state || null,
        district: form.district || null,
        annual_family_income: form.annual_family_income ? Number(form.annual_family_income) : null,
        existing_loan: form.existing_loan === "yes",
        purpose: form.purpose || null,
        project_type: form.project_type || null,
        project_cost: form.project_cost ? Number(form.project_cost) : null,
        loan_required: form.loan_required ? Number(form.loan_required) : null,
        education_status: form.purpose === "education" ? form.education_status || null : null,
      };
      const out = await api<{ recommendations: Rec[] }>("/api/v1/assessments/recommend", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setRecs(out.recommendations || []);
      setSelected(out.recommendations?.[0] || null);
      setStep(3);
    } catch {
      setError(messages.error);
    } finally {
      setLoading(false);
    }
  }

  async function calcEmi(rec: Rec) {
    if (!form.loan_required || !rec.interest_rate || !rec.tenure) {
      setEmi(null);
      return;
    }
    const out = await api("/api/v1/finance/emi", {
      method: "POST",
      body: JSON.stringify({
        principal: Number(form.loan_required),
        annual_rate_percent: rec.interest_rate,
        tenure_months: rec.tenure,
        moratorium_months: rec.moratorium || 0,
      }),
    });
    setEmi(out);
  }

  async function useGeo() {
    setLocMode("geo");
    if (!navigator.geolocation) {
      setError("Geolocation is not supported in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        update("latitude", String(pos.coords.latitude));
        update("longitude", String(pos.coords.longitude));
      },
      () => {
        setError("Location permission denied. You can continue with manual location.");
        setLocMode("manual");
      }
    );
  }

  async function searchPartners() {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const body: any = {
        scheme_id: selected.scheme_id,
        state: form.state || null,
        district: form.district || null,
        city: form.city || null,
        address: form.address || null,
        pin_code: form.pin_code || null,
      };
      if (form.latitude && form.longitude) {
        body.latitude = Number(form.latitude);
        body.longitude = Number(form.longitude);
      }
      const out = await api("/api/v1/partners/search", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setPartners(out);
    } catch {
      setError(messages.error);
    } finally {
      setLoading(false);
    }
  }

  const stepLabel = useMemo(() => {
    return [messages.stepProfile, messages.stepFinance, messages.stepProject, messages.stepResults][step];
  }, [messages, step]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-display text-3xl text-[var(--navy)]">{messages.findScheme}</h1>
      <p className="mt-2 text-[var(--muted)]">{stepLabel}</p>
      <div className="progress mt-4">
        <span style={{ width: `${progress}%` }} />
      </div>

      {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-red-700">{error}</p>}

      {step < 3 && (
        <div className="panel mt-6">
          <label className="label">{messages.nlpPlaceholder}</label>
          <textarea
            className="input min-h-24"
            value={nlpText}
            onChange={(e) => setNlpText(e.target.value)}
            placeholder={messages.nlpHint}
          />
          <button type="button" className="btn btn-secondary mt-3" onClick={parseNlp} disabled={loading}>
            {messages.parse}
          </button>
        </div>
      )}

      {step === 0 && (
        <div className="panel mt-6 grid gap-4 md:grid-cols-2">
          <div>
            <label className="label">{messages.age}</label>
            <input className="input" value={form.age} onChange={(e) => update("age", e.target.value)} />
          </div>
          <div>
            <label className="label">{messages.category}</label>
            <select className="select" value={form.category} onChange={(e) => update("category", e.target.value)}>
              <option value="SC">SC</option>
              <option value="ST">ST</option>
              <option value="OBC">OBC</option>
              <option value="Other">Other</option>
            </select>
          </div>
          <div>
            <label className="label">{messages.state}</label>
            <input className="input" value={form.state} onChange={(e) => update("state", e.target.value)} />
          </div>
          <div>
            <label className="label">{messages.district}</label>
            <input className="input" value={form.district} onChange={(e) => update("district", e.target.value)} />
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="panel mt-6 grid gap-4 md:grid-cols-2">
          <div>
            <label className="label">{messages.income}</label>
            <input
              className="input"
              value={form.annual_family_income}
              onChange={(e) => update("annual_family_income", e.target.value)}
            />
          </div>
          <div>
            <label className="label">{messages.existingLoan}</label>
            <select
              className="select"
              value={form.existing_loan}
              onChange={(e) => update("existing_loan", e.target.value)}
            >
              <option value="no">{messages.no}</option>
              <option value="yes">{messages.yes}</option>
            </select>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="panel mt-6 grid gap-4 md:grid-cols-2">
          <div>
            <label className="label">{messages.purpose}</label>
            <select className="select" value={form.purpose} onChange={(e) => update("purpose", e.target.value)}>
              <option value="business">{messages.business}</option>
              <option value="education">{messages.education}</option>
              <option value="self-employment">{messages.selfEmployment}</option>
              <option value="other">{messages.other}</option>
            </select>
          </div>
          <div>
            <label className="label">{messages.projectType}</label>
            <input
              className="input"
              value={form.project_type}
              onChange={(e) => update("project_type", e.target.value)}
            />
          </div>
          <div>
            <label className="label">{messages.projectCost}</label>
            <input
              className="input"
              value={form.project_cost}
              onChange={(e) => update("project_cost", e.target.value)}
            />
          </div>
          <div>
            <label className="label">{messages.loanRequired}</label>
            <input
              className="input"
              value={form.loan_required}
              onChange={(e) => update("loan_required", e.target.value)}
            />
          </div>
          {form.purpose === "education" && (
            <div className="md:col-span-2">
              <label className="label">{messages.educationStatus}</label>
              <input
                className="input"
                value={form.education_status}
                onChange={(e) => update("education_status", e.target.value)}
              />
            </div>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="mt-6 space-y-4">
          <h2 className="font-display text-2xl text-[var(--navy)]">{messages.recommended}</h2>
          {recs.length === 0 && <p className="panel">{messages.emptySchemes}</p>}
          {recs.map((r) => (
            <button
              key={r.scheme_id}
              type="button"
              className={`panel w-full text-left ${selected?.scheme_id === r.scheme_id ? "ring-2 ring-[var(--saffron)]" : ""}`}
              onClick={() => {
                setSelected(r);
                calcEmi(r);
              }}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xl font-semibold">{r.name}</h3>
                <span className="text-sm text-[var(--muted)]">Score {r.score}</span>
              </div>
              <p className="mt-2 text-sm text-[var(--green)]">{messages.noGuarantee}</p>
            </button>
          ))}

          {selected && (
            <div className="panel space-y-4">
              <h3 className="font-display text-xl">{messages.why}</h3>
              <ul className="space-y-2">
                {selected.why.map((w, i) => (
                  <li key={i} className="flex gap-2">
                    <span>{w.status === "pass" ? "✓" : w.status === "warning" ? "⚠" : "✗"}</span>
                    <span>{w.text}</span>
                  </li>
                ))}
              </ul>

              <div>
                <h4 className="font-semibold">{messages.calculator} ({messages.estimated})</h4>
                {selected.interest_rate == null || selected.tenure == null ? (
                  <p className="text-[var(--muted)]">{messages.notAvailable}</p>
                ) : emi ? (
                  <div className="mt-2 grid gap-2 md:grid-cols-3">
                    <div>EMI: ₹{emi.emi}</div>
                    <div>Interest: ₹{emi.total_interest}</div>
                    <div>Total: ₹{emi.total_repayment}</div>
                  </div>
                ) : (
                  <button type="button" className="btn btn-secondary mt-2" onClick={() => calcEmi(selected)}>
                    Calculate
                  </button>
                )}
              </div>

              <div>
                <h4 className="font-semibold">{messages.documents}</h4>
                {selected.required_documents?.length ? (
                  <ul className="mt-2 space-y-1">
                    {selected.required_documents.map((d) => (
                      <li key={d}>☐ {d}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[var(--muted)]">{messages.notAvailable}</p>
                )}
              </div>

              <div>
                <h4 className="font-semibold">{messages.guidance}</h4>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
                  <li>Confirm your eligibility.</li>
                  <li>Identify the recommended channel partner.</li>
                  <li>Contact/visit the partner.</li>
                  <li>Carry required documents.</li>
                  <li>Ask the partner to confirm current scheme availability.</li>
                  <li>Complete the official application process.</li>
                </ol>
              </div>

              <div>
                <h4 className="font-semibold">Official Sources</h4>
                <p className="text-sm text-[var(--muted)]">
                  {messages.lastVerified}: {selected.last_verified || messages.notAvailable} ·{" "}
                  {messages.freshness}: {selected.freshness}
                </p>
                {selected.source_url && (
                  <a className="mt-2 inline-block text-[var(--navy)] underline" href={selected.source_url} target="_blank" rel="noreferrer">
                    {messages.officialSource}
                  </a>
                )}
                <ul className="mt-2 space-y-1 text-sm">
                  {selected.citations?.map((c, i) => (
                    <li key={i}>
                      {c.field_name || "Info"}:{" "}
                      <a className="underline" href={c.source_url} target="_blank" rel="noreferrer">
                        {c.source_title || messages.officialSource}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border-t border-[var(--border)] pt-4">
                <h4 className="font-semibold">{messages.findPartner}</h4>
                <p className="text-sm text-[var(--muted)]">{messages.partnerPrivacy}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className="btn btn-secondary" onClick={useGeo}>
                    📍 {messages.useLocation}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={() => setLocMode("manual")}>
                    {messages.manualLocation}
                  </button>
                </div>
                {locMode === "manual" && (
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <input className="input" placeholder={messages.address} value={form.address} onChange={(e) => update("address", e.target.value)} />
                    <input className="input" placeholder={messages.city} value={form.city} onChange={(e) => update("city", e.target.value)} />
                    <input className="input" placeholder={messages.district} value={form.district} onChange={(e) => update("district", e.target.value)} />
                    <input className="input" placeholder={messages.state} value={form.state} onChange={(e) => update("state", e.target.value)} />
                    <input className="input" placeholder={messages.pin} value={form.pin_code} onChange={(e) => update("pin_code", e.target.value)} />
                  </div>
                )}
                {(form.latitude || form.longitude) && (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Lat {form.latitude}, Lon {form.longitude}
                  </p>
                )}
                <button type="button" className="btn btn-primary mt-3" onClick={searchPartners} disabled={loading}>
                  {messages.searchPartners}
                </button>
                {partners && (
                  <div className="mt-4 space-y-3">
                    <p className="text-sm">
                      Radius used: {partners.matched_radius_km ?? "region"} km · Found {partners.count}
                    </p>
                    {partners.count === 0 && <p>{partners.message || messages.noPartners}</p>}
                    {partners.partners?.map((p: any) => (
                      <div key={p.id} className="rounded-lg border border-[var(--border)] p-3">
                        <div className="font-semibold">{p.name}</div>
                        <div className="text-sm text-[var(--muted)]">
                          {p.distance_km != null ? `${p.distance_km} ${messages.kmAway}` : `${p.district || ""} ${p.state || ""}`}
                        </div>
                        <ul className="mt-2 text-sm">
                          {(p.reasons || []).map((r: string, idx: number) => (
                            <li key={idx}>✓ {r}</li>
                          ))}
                        </ul>
                        {p.source_url && (
                          <a className="mt-2 inline-block text-sm underline" href={p.source_url} target="_blank" rel="noreferrer">
                            {messages.officialSource}
                          </a>
                        )}
                        <p className="mt-1 text-xs text-[var(--muted)]">
                          {p.partner_operational_status?.note || p.partner_operational_status?.status}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mt-6 flex justify-between">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={step === 0 || loading}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          {messages.back}
        </button>
        {step < 2 && (
          <button type="button" className="btn btn-primary" onClick={() => setStep((s) => s + 1)}>
            {messages.next}
          </button>
        )}
        {step === 2 && (
          <button type="button" className="btn btn-primary" onClick={runAssessment} disabled={loading}>
            {loading ? messages.loading : messages.continue}
          </button>
        )}
      </div>
    </div>
  );
}
