export type LocaleCode = "en" | "hi";

type Opt = { value: string; en: string; hi: string };

export const CATEGORY_OPTIONS: Opt[] = [
  { value: "SC", en: "SC (Scheduled Caste)", hi: "एससी (अनुसूचित जाति)" },
  { value: "ST", en: "ST (Scheduled Tribe)", hi: "एसटी (अनुसूचित जनजाति)" },
  { value: "OBC", en: "OBC (Other Backward Class)", hi: "ओबीसी (अन्य पिछड़ा वर्ग)" },
  { value: "Other", en: "Other", hi: "अन्य" },
];

export const GENDER_OPTIONS: Opt[] = [
  { value: "male", en: "Male", hi: "पुरुष" },
  { value: "female", en: "Female", hi: "महिला" },
  { value: "prefer_not_to_say", en: "Prefer not to say", hi: "कहना नहीं चाहते" },
];

export const PURPOSE_OPTIONS: Opt[] = [
  { value: "business", en: "Business", hi: "व्यवसाय" },
  { value: "self-employment", en: "Self-employment", hi: "स्वरोजगार" },
  { value: "education", en: "Education", hi: "शिक्षा" },
  { value: "other", en: "Other", hi: "अन्य" },
];

export const PROJECT_TYPE_OPTIONS: Opt[] = [
  { value: "dairy", en: "Dairy / Animal husbandry", hi: "डेयरी / पशुपालन" },
  { value: "kirana", en: "Kirana / Grocery shop", hi: "किराना / किराना दुकान" },
  { value: "tailoring", en: "Tailoring / Boutique", hi: "सिलाई / बुटीक" },
  { value: "beauty_parlour", en: "Beauty parlour / Salon", hi: "ब्यूटी पार्लर / सैलून" },
  { value: "transport", en: "Transport / Vehicle", hi: "परिवहन / वाहन" },
  { value: "agriculture", en: "Agriculture / Farming", hi: "कृषि / खेती" },
  { value: "poultry", en: "Poultry", hi: "मुर्गी पालन" },
  { value: "micro_enterprise", en: "Micro enterprise / Small business", hi: "सूक्ष्म उद्यम / छोटा व्यवसाय" },
  { value: "manufacturing", en: "Manufacturing / Workshop", hi: "विनिर्माण / कार्यशाला" },
  { value: "services", en: "Services / Repair", hi: "सेवाएँ / मरम्मत" },
  { value: "education_loan", en: "Education / Tuition fees", hi: "शिक्षा / ट्यूशन शुल्क" },
  { value: "other", en: "Other", hi: "अन्य" },
];

export const EDUCATION_STATUS_OPTIONS: Opt[] = [
  { value: "class_10", en: "Class 10", hi: "कक्षा 10" },
  { value: "class_12", en: "Class 12", hi: "कक्षा 12" },
  { value: "diploma", en: "Diploma", hi: "डिप्लोमा" },
  { value: "undergraduate", en: "Undergraduate (UG)", hi: "स्नातक (यूजी)" },
  { value: "postgraduate", en: "Postgraduate (PG)", hi: "स्नातकोत्तर (पीजी)" },
  { value: "professional", en: "Professional course (Engineering / Medical / Law / etc.)", hi: "व्यावसायिक पाठ्यक्रम (इंजीनियरिंग / चिकित्सा / कानून आदि)" },
  { value: "vocational", en: "Vocational / Skill course", hi: "व्यावसायिक / कौशल पाठ्यक्रम" },
  { value: "other", en: "Other", hi: "अन्य" },
];

export const EXISTING_LOAN_OPTIONS: Opt[] = [
  { value: "no", en: "No", hi: "नहीं" },
  { value: "yes", en: "Yes", hi: "हाँ" },
];

export const AGE_OPTIONS = Array.from({ length: 83 }, (_, i) => String(i + 18));

export function optLabel(opt: Opt, locale: LocaleCode) {
  return locale === "hi" ? opt.hi : opt.en;
}

/** Common state display names in Hindi (values stay English for matching). */
export const STATE_LABEL_HI: Record<string, string> = {
  "Andhra Pradesh": "आंध्र प्रदेश",
  "Arunachal Pradesh": "अरुणाचल प्रदेश",
  Assam: "असम",
  Bihar: "बिहार",
  "Chandigarh (UT)": "चंडीगढ़",
  Chhattisgarh: "छत्तीसगढ़",
  "Dadra and Nagar Haveli (UT)": "दादरा और नगर हवेली",
  "Daman and Diu (UT)": "दमन और दीव",
  "Delhi (NCT)": "दिल्ली",
  Goa: "गोवा",
  Gujarat: "गुजरात",
  Haryana: "हरियाणा",
  "Himachal Pradesh": "हिमाचल प्रदेश",
  "Jammu and Kashmir": "जम्मू और कश्मीर",
  Jharkhand: "झारखंड",
  Karnataka: "कर्नाटक",
  Kerala: "केरल",
  "Lakshadweep (UT)": "लक्षद्वीप",
  "Madhya Pradesh": "मध्य प्रदेश",
  Maharashtra: "महाराष्ट्र",
  Manipur: "मणिपुर",
  Meghalaya: "मेघालय",
  Mizoram: "मिज़ोरम",
  Nagaland: "नागालैंड",
  Odisha: "ओडिशा",
  "Puducherry (UT)": "पुडुचेरी",
  Punjab: "पंजाब",
  Rajasthan: "राजस्थान",
  Sikkim: "सिक्किम",
  "Tamil Nadu": "तमिलनाडु",
  Telangana: "तेलंगाना",
  Tripura: "त्रिपुरा",
  "Uttar Pradesh": "उत्तर प्रदेश",
  Uttarakhand: "उत्तराखंड",
  "West Bengal": "पश्चिम बंगाल",
  "Andaman and Nicobar Islands (UT)": "अंडमान और निकोबार द्वीप समूह",
};

export function stateLabel(state: string, locale: LocaleCode) {
  if (locale !== "hi") return state;
  return STATE_LABEL_HI[state] ? `${STATE_LABEL_HI[state]} (${state})` : state;
}
