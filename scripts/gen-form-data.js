const fs = require("fs");
const path = require("path");

const raw = JSON.parse(fs.readFileSync(path.join("frontend", "src", "data", "india-raw.json"), "utf8"));
const map = {};
for (const s of raw.states) {
  map[s.state] = s.districts.slice().sort((a, b) => a.localeCompare(b));
}
const states = Object.keys(map).sort((a, b) => a.localeCompare(b));

const indiaTs = `/** Indian states/UTs and districts for cascading dropdowns. */
export const INDIA_STATES = ${JSON.stringify(states, null, 2)} as const;

export const DISTRICTS_BY_STATE: Record<string, string[]> = ${JSON.stringify(map, null, 2)};

export function districtsForState(state: string): string[] {
  return DISTRICTS_BY_STATE[state] || [];
}
`;

fs.writeFileSync(path.join("frontend", "src", "data", "indiaLocations.ts"), indiaTs);

const formTs = `export const CATEGORY_OPTIONS = [
  { value: "SC", label: "SC (Scheduled Caste)" },
  { value: "ST", label: "ST (Scheduled Tribe)" },
  { value: "OBC", label: "OBC (Other Backward Class)" },
  { value: "Other", label: "Other" },
] as const;

export const PURPOSE_OPTIONS = [
  { value: "business", label: "Business" },
  { value: "self-employment", label: "Self-employment" },
  { value: "education", label: "Education" },
  { value: "other", label: "Other" },
] as const;

export const PROJECT_TYPE_OPTIONS = [
  { value: "dairy", label: "Dairy / Animal husbandry" },
  { value: "kirana", label: "Kirana / Grocery shop" },
  { value: "tailoring", label: "Tailoring / Boutique" },
  { value: "beauty_parlour", label: "Beauty parlour / Salon" },
  { value: "transport", label: "Transport / Vehicle" },
  { value: "agriculture", label: "Agriculture / Farming" },
  { value: "poultry", label: "Poultry" },
  { value: "micro_enterprise", label: "Micro enterprise / Small business" },
  { value: "manufacturing", label: "Manufacturing / Workshop" },
  { value: "services", label: "Services / Repair" },
  { value: "education_loan", label: "Education / Tuition fees" },
  { value: "other", label: "Other" },
] as const;

export const EDUCATION_STATUS_OPTIONS = [
  { value: "class_10", label: "Class 10" },
  { value: "class_12", label: "Class 12" },
  { value: "diploma", label: "Diploma" },
  { value: "undergraduate", label: "Undergraduate (UG)" },
  { value: "postgraduate", label: "Postgraduate (PG)" },
  { value: "professional", label: "Professional course (Engineering / Medical / Law / etc.)" },
  { value: "vocational", label: "Vocational / Skill course" },
  { value: "other", label: "Other" },
] as const;

export const EXISTING_LOAN_OPTIONS = [
  { value: "no", label: "No" },
  { value: "yes", label: "Yes" },
] as const;

export const AGE_OPTIONS = Array.from({ length: 83 }, (_, i) => String(i + 18));
`;

fs.writeFileSync(path.join("frontend", "src", "data", "formOptions.ts"), formTs);
console.log("ok", states.length);
