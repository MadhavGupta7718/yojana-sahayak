"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";

const PartnerMap = dynamic(() => import("@/components/PartnerMap"), { ssr: false });

type Messages = Record<string, string>;

type Rec = {
  scheme_id: number;
  name: string;
  score: number;
  why: { status: string; text: string }[];
  gaps?: { field: string; your_value: unknown; scheme_requires: unknown; message: string }[];
  blocking_reasons?: string[];
  eligible?: boolean;
  interest_rate: number | null;
  max_loan: number | null;
  min_loan: number | null;
  max_income: number | null;
  tenure: number | null;
  moratorium: number | null;
  required_documents: string[] | null;
  source_url: string | null;
  last_verified: string | null;
  freshness: string;
  disclaimer: string;
  purpose?: string | null;
  scheme_type?: string | null;
  citations: { field_name: string | null; source_url: string; source_title: string | null }[];
  unavailable_fields: string[];
  application_process?: string | null;
};

function money(n: number | null | undefined) {
  if (n == null) return "Not published by official source";
  return `₹${Number(n).toLocaleString("en-IN")}`;
}

function humanField(name: string | null | undefined) {
  if (!name) return "Scheme information";
  const map: Record<string, string> = {
    max_loan: "Maximum loan amount",
    min_loan: "Minimum loan amount",
    interest_rate: "Interest rate",
    tenure: "Repayment tenure",
    moratorium: "Moratorium period",
    max_income: "Income limit",
    name: "Scheme name",
    description: "Scheme description",
    required_documents: "Required documents",
    application_process: "Application process",
  };
  return map[name] || name.replace(/_/g, " ");
}

export default function FindClient({ messages }: { messages: Messages }) {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [nlpText, setNlpText] = useState("");
  const [nlpNote, setNlpNote] = useState<string | null>(null);
  const [recs, setRecs] = useState<Rec[]>([]);
  const [nearMisses, setNearMisses] = useState<Rec[]>([]);
  const [matchStatus, setMatchStatus] = useState<"matched" | "no_match" | null>(null);
  const [matchMessage, setMatchMessage] = useState<string | null>(null);
  const [selected, setSelected] = useState<Rec | null>(null);
  const [emi, setEmi] = useState<any>(null);
  const [partners, setPartners] = useState<any>(null);
  const [locStatus, setLocStatus] = useState<string | null>(null);
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
    pin_code: "",
    latitude: "" as string,
    longitude: "" as string,
  });

  const progress = ((step + 1) / 4) * 100;

  function update(key: string, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    setFieldErrors((e) => {
      const next = { ...e };
      delete next[key];
      return next;
    });
  }

  function validateStep(s: number): boolean {
    const errs: Record<string, string> = {};
    if (s === 0) {
      if (!form.age || Number(form.age) < 18 || Number(form.age) > 100) errs.age = "Enter a valid age (18–100).";
      if (!form.category) errs.category = "Select category.";
      if (!form.state.trim()) errs.state = "State is required.";
      if (!form.district.trim()) errs.district = "District is required.";
    }
    if (s === 1) {
      if (!form.annual_family_income || Number(form.annual_family_income) <= 0) {
        errs.annual_family_income = "Enter annual family income.";
      }
    }
    if (s === 2) {
      if (!form.purpose) errs.purpose = "Select purpose.";
      if (!form.project_type.trim()) errs.project_type = "Enter project / activity type.";
      if (!form.project_cost || Number(form.project_cost) <= 0) errs.project_cost = "Enter estimated project cost.";
      if (!form.loan_required || Number(form.loan_required) <= 0) errs.loan_required = "Enter required loan amount.";
      if (form.purpose === "education" && !form.education_status.trim()) {
        errs.education_status = "Enter education status for education loans.";
      }
    }
    setFieldErrors(errs);
    if (Object.keys(errs).length) {
      setError("Please complete the required fields before continuing.");
      return false;
    }
    setError(null);
    return true;
  }

  async function parseNlp() {
    if (!nlpText.trim()) {
      setError("Type your need first, then click Understand my text.");
      return;
    }
    setLoading(true);
    setError(null);
    setNlpNote(null);
    try {
      const out = await api<{ extracted: Record<string, unknown>; notes?: string }>("/api/v1/nlp/parse", {
        method: "POST",
        body: JSON.stringify({ text: nlpText }),
      });
      const e = out.extracted || {};
      const filled: string[] = [];
      const nextForm = { ...form };
      if (e.purpose) {
        nextForm.purpose = String(e.purpose) === "agriculture" ? "business" : String(e.purpose);
        filled.push("purpose");
      }
      if (e.project_type) {
        nextForm.project_type = String(e.project_type);
        filled.push("project type");
      }
      if (e.category) {
        nextForm.category = String(e.category);
        filled.push("category");
      }
      if (e.age != null) {
        nextForm.age = String(e.age);
        filled.push("age");
      }
      if (e.loan_required != null) {
        nextForm.loan_required = String(e.loan_required);
        filled.push("loan amount");
      }
      if (e.annual_family_income != null) {
        nextForm.annual_family_income = String(e.annual_family_income);
        filled.push("income");
      }
      setForm(nextForm);
      setFieldErrors({});
      if (filled.length === 0) {
        setNlpNote("Could not extract clear details. Please fill the form fields manually.");
      } else {
        setNlpNote(`Filled from your text: ${filled.join(", ")}. Please review and complete remaining required fields.`);
      }
    } catch {
      setError("Could not understand the text. Please fill the form manually.");
    } finally {
      setLoading(false);
    }
  }

  async function runAssessment() {
    if (!validateStep(2)) return;
    setLoading(true);
    setError(null);
    try {
      const body = {
        age: Number(form.age),
        category: form.category,
        state: form.state,
        district: form.district,
        annual_family_income: Number(form.annual_family_income),
        existing_loan: form.existing_loan === "yes",
        purpose: form.purpose,
        project_type: form.project_type,
        project_cost: Number(form.project_cost),
        loan_required: Number(form.loan_required),
        education_status: form.purpose === "education" ? form.education_status : null,
      };
      const out = await api<{
        recommendations: Rec[];
        near_misses?: Rec[];
        match_status?: "matched" | "no_match";
        message?: string | null;
        disclaimer: string;
      }>("/api/v1/assessments/recommend", {
        method: "POST",
        body: JSON.stringify(body),
      });
      const matched = out.recommendations || [];
      const misses = out.near_misses || [];
      setRecs(matched);
      setNearMisses(misses);
      setMatchStatus(out.match_status || (matched.length ? "matched" : "no_match"));
      setMatchMessage(out.message || null);
      const first = matched[0] || misses[0] || null;
      setSelected(first);
      setPartners(null);
      setEmi(null);
      if (first && matched.length) await calcEmi(first);
      setStep(3);
    } catch {
      setError(messages.error);
    } finally {
      setLoading(false);
    }
  }

  async function calcEmi(rec: Rec) {
    if (!form.loan_required || rec.interest_rate == null || rec.tenure == null) {
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

  function useGeo() {
    setLocStatus(null);
    if (!navigator.geolocation) {
      setError("This browser does not support location. Enter state and district instead.");
      return;
    }
    setLocStatus("Detecting your location…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        update("latitude", String(pos.coords.latitude));
        update("longitude", String(pos.coords.longitude));
        setLocStatus("Location detected. You can now search nearby partners.");
        setError(null);
      },
      () => {
        setLocStatus(null);
        setError("Location permission denied. Enter state and district to continue.");
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  }

  async function searchPartners() {
    if (!selected) return;
    if (!form.latitude && !form.longitude && !form.state.trim()) {
      setError("Use automatic location or enter at least your state to search partners.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const body: any = {
        scheme_id: selected.scheme_id,
        state: form.state || null,
        district: form.district || null,
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
    <div className="page-wrap">
      <h1 className="text-navy font-display">{messages.findScheme}</h1>
      <p className="mt-2 text-muted">{stepLabel}</p>
      <div className="progress mt-4">
        <span style={{ width: `${progress}%` }} />
      </div>

      {error && <p className="error-box">{error}</p>}

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
          {nlpNote && <p className="mt-3 text-sm" style={{ color: "var(--green)" }}>{nlpNote}</p>}
        </div>
      )}

      {step === 0 && (
        <div className="panel mt-6 form-grid">
          <div>
            <label className="label">{messages.age} *</label>
            <input className="input" value={form.age} onChange={(e) => update("age", e.target.value)} required />
            {fieldErrors.age && <p className="field-error">{fieldErrors.age}</p>}
          </div>
          <div>
            <label className="label">{messages.category} *</label>
            <select className="select" value={form.category} onChange={(e) => update("category", e.target.value)}>
              <option value="SC">SC</option>
              <option value="ST">ST</option>
              <option value="OBC">OBC</option>
              <option value="Other">Other</option>
            </select>
            {fieldErrors.category && <p className="field-error">{fieldErrors.category}</p>}
          </div>
          <div>
            <label className="label">{messages.state} *</label>
            <input className="input" value={form.state} onChange={(e) => update("state", e.target.value)} required />
            {fieldErrors.state && <p className="field-error">{fieldErrors.state}</p>}
          </div>
          <div>
            <label className="label">{messages.district} *</label>
            <input className="input" value={form.district} onChange={(e) => update("district", e.target.value)} required />
            {fieldErrors.district && <p className="field-error">{fieldErrors.district}</p>}
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="panel mt-6 form-grid">
          <div>
            <label className="label">{messages.income} *</label>
            <input
              className="input"
              value={form.annual_family_income}
              onChange={(e) => update("annual_family_income", e.target.value)}
              required
            />
            {fieldErrors.annual_family_income && <p className="field-error">{fieldErrors.annual_family_income}</p>}
          </div>
          <div>
            <label className="label">{messages.existingLoan}</label>
            <select className="select" value={form.existing_loan} onChange={(e) => update("existing_loan", e.target.value)}>
              <option value="no">{messages.no}</option>
              <option value="yes">{messages.yes}</option>
            </select>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="panel mt-6 form-grid">
          <div>
            <label className="label">{messages.purpose} *</label>
            <select className="select" value={form.purpose} onChange={(e) => update("purpose", e.target.value)}>
              <option value="business">{messages.business}</option>
              <option value="education">{messages.education}</option>
              <option value="self-employment">{messages.selfEmployment}</option>
              <option value="other">{messages.other}</option>
            </select>
          </div>
          <div>
            <label className="label">{messages.projectType} *</label>
            <input className="input" value={form.project_type} onChange={(e) => update("project_type", e.target.value)} />
            {fieldErrors.project_type && <p className="field-error">{fieldErrors.project_type}</p>}
          </div>
          <div>
            <label className="label">{messages.projectCost} *</label>
            <input className="input" value={form.project_cost} onChange={(e) => update("project_cost", e.target.value)} />
            {fieldErrors.project_cost && <p className="field-error">{fieldErrors.project_cost}</p>}
          </div>
          <div>
            <label className="label">{messages.loanRequired} *</label>
            <input className="input" value={form.loan_required} onChange={(e) => update("loan_required", e.target.value)} />
            {fieldErrors.loan_required && <p className="field-error">{fieldErrors.loan_required}</p>}
          </div>
          {form.purpose === "education" && (
            <div className="span-2">
              <label className="label">{messages.educationStatus} *</label>
              <input className="input" value={form.education_status} onChange={(e) => update("education_status", e.target.value)} />
              {fieldErrors.education_status && <p className="field-error">{fieldErrors.education_status}</p>}
            </div>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="mt-6 space-y">
          <div className={`result-banner panel ${matchStatus === "no_match" ? "panel-warn" : ""}`}>
            <h2 className="font-display text-navy" style={{ margin: 0, fontSize: "1.45rem" }}>
              {matchStatus === "matched" ? "Matching schemes for you" : "No scheme matches your need"}
            </h2>
            <p className="text-sm text-muted mt-2" style={{ marginBottom: 0 }}>
              {matchMessage ||
                (matchStatus === "matched"
                  ? "These are guidance results based on published eligibility rules. This is not a loan approval."
                  : "No published scheme currently fits your details. Closest options below explain exactly where you fall short.")}
            </p>
          </div>

          {matchStatus === "matched" && (
            <div className="scheme-list">
              {recs.map((r, idx) => (
                <button
                  key={r.scheme_id}
                  type="button"
                  className={`scheme-card ${selected?.scheme_id === r.scheme_id ? "is-selected" : ""}`}
                  onClick={() => {
                    setSelected(r);
                    calcEmi(r);
                    setPartners(null);
                  }}
                >
                  <div className="scheme-card__top">
                    <span className="scheme-rank">Option {idx + 1}</span>
                    <span className="scheme-match">Match score {r.score}</span>
                  </div>
                  <h3>{r.name}</h3>
                  <div className="scheme-facts">
                    <span>Max loan: {money(r.max_loan)}</span>
                    <span>Interest: {r.interest_rate != null ? `${r.interest_rate}%` : "Not published"}</span>
                    <span>Tenure: {r.tenure != null ? `${r.tenure} months` : "Not published"}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {matchStatus === "no_match" && nearMisses.length > 0 && (
            <div className="scheme-list">
              <p className="text-sm text-muted" style={{ margin: 0 }}>
                Closest scheme(s) — not available for you right now:
              </p>
              {nearMisses.map((r, idx) => (
                <button
                  key={r.scheme_id}
                  type="button"
                  className={`scheme-card scheme-card--blocked ${selected?.scheme_id === r.scheme_id ? "is-selected" : ""}`}
                  onClick={() => {
                    setSelected(r);
                    setEmi(null);
                    setPartners(null);
                  }}
                >
                  <div className="scheme-card__top">
                    <span className="scheme-rank">Best reference {idx + 1}</span>
                    <span className="scheme-blocked">Cannot avail</span>
                  </div>
                  <h3>{r.name}</h3>
                  <ul className="why-list compact">
                    {(r.blocking_reasons || r.gaps?.map((g) => g.message) || []).slice(0, 3).map((msg, i) => (
                      <li key={i} className="why-fail">{msg}</li>
                    ))}
                  </ul>
                </button>
              ))}
            </div>
          )}

          {matchStatus === "no_match" && nearMisses.length === 0 && (
            <p className="panel">{messages.emptySchemes}</p>
          )}

          {selected && (
            <div className="panel space-y result-detail">
              <div>
                <h3 className="font-display text-navy" style={{ marginTop: 0 }}>{selected.name}</h3>
                {selected.eligible === false || matchStatus === "no_match" ? (
                  <p className="text-sm" style={{ color: "#b91c1c" }}>
                    You cannot currently avail this scheme. Review the gaps below.
                  </p>
                ) : (
                  <p className="text-sm" style={{ color: "var(--green)" }}>{messages.noGuarantee}</p>
                )}
              </div>

              {(selected.gaps?.length || selected.blocking_reasons?.length) ? (
                <section className="gap-box">
                  <h4>Where you fall short</h4>
                  <ul className="why-list">
                    {(selected.gaps?.length
                      ? selected.gaps.map((g) => g.message)
                      : selected.blocking_reasons || []
                    ).map((msg, i) => (
                      <li key={i} className="why-fail">{msg}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <section>
                <h4>{matchStatus === "no_match" ? "Eligibility check details" : "Why this scheme?"}</h4>
                <ul className="why-list">
                  {selected.why.map((w, i) => (
                    <li key={i} className={`why-${w.status}`}>
                      <strong>{w.status === "pass" ? "Match" : w.status === "warning" ? "Need more info" : "Does not match"}:</strong>{" "}
                      {w.text}
                    </li>
                  ))}
                </ul>
              </section>

              <section>
                <h4>Key scheme facts</h4>
                <div className="fact-grid">
                  <div><span>Maximum loan</span><strong>{money(selected.max_loan)}</strong></div>
                  <div><span>Interest rate (estimated)</span><strong>{selected.interest_rate != null ? `${selected.interest_rate}%` : "Not published"}</strong></div>
                  <div><span>Repayment tenure</span><strong>{selected.tenure != null ? `${selected.tenure} months` : "Not published"}</strong></div>
                  <div><span>Moratorium</span><strong>{selected.moratorium != null ? `${selected.moratorium} months` : "Not published"}</strong></div>
                  <div><span>Income limit</span><strong>{money(selected.max_income)}</strong></div>
                  <div><span>Data freshness</span><strong>{selected.freshness}</strong></div>
                </div>
              </section>

              <section>
                <h4>{messages.calculator}</h4>
                <p className="text-sm text-muted" style={{ marginTop: "-0.35rem" }}>
                  {messages.estimated} values only — confirm with the channel partner.
                </p>
                {selected.eligible === false || matchStatus === "no_match" ? (
                  <p className="text-muted">EMI estimate is shown only for schemes you appear eligible for.</p>
                ) : selected.interest_rate == null || selected.tenure == null ? (
                  <p className="text-muted">{messages.notAvailable}</p>
                ) : emi ? (
                  <div className="fact-grid">
                    <div><span>Estimated EMI</span><strong>₹{Number(emi.emi).toLocaleString("en-IN")}</strong></div>
                    <div><span>Total interest</span><strong>₹{Number(emi.total_interest).toLocaleString("en-IN")}</strong></div>
                    <div><span>Total repayment</span><strong>₹{Number(emi.total_repayment).toLocaleString("en-IN")}</strong></div>
                  </div>
                ) : (
                  <button type="button" className="btn btn-secondary" onClick={() => calcEmi(selected)}>
                    Calculate estimate
                  </button>
                )}
              </section>

              <section>
                <h4>{messages.documents}</h4>
                {selected.required_documents?.length ? (
                  <ul className="doc-list">
                    {selected.required_documents.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted">Document list is not available from the official source yet. Confirm with the channel partner.</p>
                )}
              </section>

              <section>
                <h4>{messages.guidance}</h4>
                <ol className="guide-list">
                  <li>Confirm eligibility on the official scheme page.</li>
                  <li>Find an authorized channel partner below.</li>
                  <li>Contact or visit the partner with your documents.</li>
                  <li>Ask the partner to confirm current scheme availability.</li>
                  <li>Complete the official application only through the partner.</li>
                </ol>
                {selected.application_process && <p className="text-sm text-muted mt-2">{selected.application_process}</p>}
              </section>

              <section className="source-box">
                <h4>Official sources (verify here)</h4>
                <p className="text-sm text-muted">
                  Last verified: {selected.last_verified ? new Date(selected.last_verified).toLocaleDateString("en-IN") : messages.notAvailable}
                </p>
                {selected.source_url ? (
                  <a className="source-link" href={selected.source_url} target="_blank" rel="noreferrer">
                    Open main official scheme source
                  </a>
                ) : (
                  <p className="text-muted">Main source URL unavailable.</p>
                )}
                <ul className="source-list">
                  {(selected.citations?.length ? selected.citations : []).map((c, i) => (
                    <li key={i}>
                      <span>{humanField(c.field_name)}</span>
                      <a href={c.source_url} target="_blank" rel="noreferrer">
                        {c.source_title || "View official source"}
                      </a>
                    </li>
                  ))}
                </ul>
                {!selected.citations?.length && selected.source_url && (
                  <p className="text-sm text-muted mt-2">Open the main official source above to verify scheme details.</p>
                )}
              </section>

              {matchStatus === "matched" && selected.eligible !== false ? (
              <section>
                <h4>{messages.findPartner}</h4>
                <p className="text-sm text-muted">{messages.partnerPrivacy}</p>
                <div className="row mt-3">
                  <button type="button" className="btn btn-secondary" onClick={useGeo}>
                    {messages.useLocation}
                  </button>
                </div>
                {locStatus && <p className="mt-2 text-sm" style={{ color: "var(--green)" }}>{locStatus}</p>}
                {(form.latitude || form.longitude) && (
                  <p className="mt-2 text-sm text-muted">
                    Detected coordinates: {Number(form.latitude).toFixed(5)}, {Number(form.longitude).toFixed(5)}
                  </p>
                )}
                <div className="form-grid mt-3">
                  <div>
                    <label className="label">{messages.state}</label>
                    <input className="input" value={form.state} onChange={(e) => update("state", e.target.value)} />
                  </div>
                  <div>
                    <label className="label">{messages.district}</label>
                    <input className="input" value={form.district} onChange={(e) => update("district", e.target.value)} />
                  </div>
                  <div>
                    <label className="label">{messages.pin}</label>
                    <input className="input" value={form.pin_code} onChange={(e) => update("pin_code", e.target.value)} />
                  </div>
                </div>
                <button type="button" className="btn btn-primary mt-3" onClick={searchPartners} disabled={loading}>
                  {messages.searchPartners}
                </button>

                {partners && (
                  <div className="mt-4 space-y">
                    <p className="text-sm">
                      {partners.mode === "geocoordinate"
                        ? `Search radius used: ${partners.matched_radius_km ?? "none"} km`
                        : "Searched by state/district (no map coordinates from you)"}
                      {" · "}Found {partners.count} partner(s)
                    </p>

                    {form.latitude && form.longitude && (
                      <PartnerMap
                        userLat={Number(form.latitude)}
                        userLon={Number(form.longitude)}
                        partners={partners.partners || []}
                        radiusKm={partners.matched_radius_km}
                      />
                    )}

                    {partners.count === 0 && <p className="panel">{partners.message || messages.noPartners}</p>}

                    {(partners.partners || []).map((p: any) => (
                      <div key={p.id} className="partner-card">
                        <div className="font-semibold">{p.name}</div>
                        <div className="text-sm text-muted">
                          {p.distance_km != null
                            ? `${p.distance_km} ${messages.kmAway}`
                            : `${p.district || ""} ${p.state || ""}`.trim() || "Location details limited"}
                        </div>
                        <ul className="why-list compact">
                          {(p.reasons || []).map((r: string, idx: number) => (
                            <li key={idx}>{r}</li>
                          ))}
                        </ul>
                        {p.source_url && (
                          <a className="source-link" href={p.source_url} target="_blank" rel="noreferrer">
                            {messages.officialSource}
                          </a>
                        )}
                        <p className="text-sm text-muted mt-2">
                          {p.partner_operational_status?.note || p.partner_operational_status?.status}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </section>
              ) : (
              <section className="gap-box">
                <h4>Next step</h4>
                <p className="text-sm" style={{ marginBottom: 0 }}>
                  Partner search is available only after a scheme matches your published eligibility criteria.
                  Adjust income, loan amount, or purpose and try again if your situation changes.
                </p>
              </section>
              )}
            </div>
          )}
        </div>
      )}

      <div className="mt-6 row between">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={step === 0 || loading}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          {messages.back}
        </button>
        {step < 2 && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              if (validateStep(step)) setStep((s) => s + 1);
            }}
          >
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
