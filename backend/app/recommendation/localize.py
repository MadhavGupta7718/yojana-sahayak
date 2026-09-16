"""Hindi/English copy for recommendation explanations and display labels."""

from __future__ import annotations

from typing import Any, Optional


def lang_code(profile_or_lang: Any) -> str:
    if isinstance(profile_or_lang, dict):
        raw = str(profile_or_lang.get("language") or "en")
    else:
        raw = str(profile_or_lang or "en")
    return "hi" if raw.lower().startswith("hi") else "en"


def fmt_money(n: Any) -> str:
    try:
        return f"₹{float(n):,.0f}"
    except (TypeError, ValueError):
        return str(n)


def freshness_label(state: str, lang: str) -> str:
    if lang != "hi":
        return state
    return {
        "Fresh": "ताज़ा",
        "Aging": "पुराना पड़ रहा",
        "Stale": "अप्रचलित",
        "Unknown": "अज्ञात",
    }.get(state, state)


def gender_label(target: Optional[str], lang: str) -> str:
    g = (target or "any").strip().lower() or "any"
    if lang == "hi":
        if g == "female":
            return "महिला"
        if g == "male":
            return "पुरुष"
        return "दोनों"
    if g == "female":
        return "Female"
    if g == "male":
        return "Male"
    return "Both"


def lifetime_label(lang: str) -> str:
    return "आजीवन" if lang == "hi" else "Lifetime"


def na_label(lang: str) -> str:
    return "उपलब्ध नहीं" if lang == "hi" else "NA"


def months_label(n: Any, lang: str) -> str:
    if n is None:
        return not_published(lang)
    return f"{n} महीने" if lang == "hi" else f"{n} months"


def not_published(lang: str) -> str:
    return "आधिकारिक स्रोत में प्रकाशित नहीं" if lang == "hi" else "Not published"


PASS_REASON = {
    "en": {
        "income": "Your family income is within the required limit.",
        "income_min": "Your family income meets the minimum published threshold.",
        "loan_amount": "Your requested loan is within the applicable limit.",
        "loan_amount_min": "Your requested loan meets the minimum published amount.",
        "category": "Your category matches the published beneficiary requirement.",
        "project_type": "Your project type matches the scheme.",
        "purpose": "Your purpose matches the scheme purpose.",
        "gender": "This scheme matches your gender eligibility.",
        "age": "Your age meets the published age condition.",
        "default": "Your details match the published condition.",
    },
    "hi": {
        "income": "आपकी पारिवारिक आय निर्धारित सीमा के भीतर है।",
        "income_min": "आपकी पारिवारिक आय न्यूनतम प्रकाशित सीमा को पूरा करती है।",
        "loan_amount": "आपका अनुरोधित ऋण लागू सीमा के भीतर है।",
        "loan_amount_min": "आपका अनुरोधित ऋण न्यूनतम प्रकाशित राशि को पूरा करता है।",
        "category": "आपकी श्रेणी प्रकाशित लाभार्थी आवश्यकता से मेल खाती है।",
        "project_type": "आपका परियोजना प्रकार योजना से मेल खाता है।",
        "purpose": "आपका उद्देश्य योजना के उद्देश्य से मेल खाता है।",
        "gender": "यह योजना आपकी लिंग-पात्रता से मेल खाती है।",
        "age": "आपकी आयु प्रकाशित आयु शर्त को पूरा करती है।",
        "default": "आपका विवरण प्रकाशित शर्त से मेल खाता है।",
    },
}


def pass_reason(rule_type: str, lang: str, *, operator: str = "") -> str:
    table = PASS_REASON["hi" if lang == "hi" else "en"]
    rt = (rule_type or "").lower()
    op = (operator or "").lower()
    if rt in {"income", "annual_family_income"} and op in {"gte", ">="}:
        return table["income_min"]
    if rt in {"loan_amount", "loan_required"} and op in {"gte", ">="}:
        return table["loan_amount_min"]
    if rt in {"income", "annual_family_income"}:
        return table["income"]
    if rt in {"loan_amount", "loan_required"}:
        return table["loan_amount"]
    if rt in table:
        return table[rt]
    return table["default"]


def missing_reason(rule_type: str, lang: str) -> str:
    if lang == "hi":
        return f"पात्रता की पुष्टि के लिए यह जानकारी ({rule_type}) आवश्यक है।"
    return f"This information ({rule_type}) is required to confirm eligibility."


def fail_reason(rule_type: str, actual: Any, expected: Any, operator: str, lang: str) -> str:
    op = (operator or "").lower()
    if lang != "hi":
        if rule_type in {"income", "annual_family_income"}:
            if op in {"lte", "<="}:
                return (
                    f"Your annual family income ({fmt_money(actual)}) is above the scheme limit "
                    f"({fmt_money(expected)}). You currently do not meet this income criterion."
                )
            if op in {"gte", ">="}:
                return (
                    f"Your annual family income ({fmt_money(actual)}) is below the minimum required "
                    f"({fmt_money(expected)})."
                )
            return f"Your income ({fmt_money(actual)}) does not meet the published income condition ({expected})."
        if rule_type in {"loan_amount", "loan_required"}:
            if op in {"lte", "<="}:
                return (
                    f"Your requested loan ({fmt_money(actual)}) is higher than the maximum allowed "
                    f"({fmt_money(expected)}) for this scheme."
                )
            if op in {"gte", ">="}:
                return (
                    f"Your requested loan ({fmt_money(actual)}) is below the minimum published amount "
                    f"({fmt_money(expected)})."
                )
            return f"Your loan amount ({fmt_money(actual)}) does not fit this scheme's loan limits."
        if rule_type == "purpose":
            return (
                f"This scheme is for '{expected}' purposes, but you asked for '{actual}'. "
                "Purpose does not match, so this scheme is not suitable."
            )
        if rule_type == "category":
            allowed = ", ".join(str(v) for v in (expected if isinstance(expected, list) else [expected]))
            return f"Your category ({actual}) is not in the allowed beneficiary categories ({allowed})."
        if rule_type == "gender":
            target = str(expected or "any").lower()
            label = "women" if target == "female" else ("men" if target == "male" else "all genders")
            return (
                f"This scheme is published for {label} beneficiaries. "
                f"Your selected gender ({actual}) does not match, so this scheme is not available for you."
            )
        if rule_type == "age":
            return f"Your age ({actual}) does not meet the published age condition for this scheme."
        if rule_type == "project_type":
            return f"Your project type ({actual}) does not match the activities covered by this scheme."
        return f"You do not meet the published '{rule_type}' condition for this scheme."

    # Hindi
    if rule_type in {"income", "annual_family_income"}:
        if op in {"lte", "<="}:
            return (
                f"आपकी वार्षिक पारिवारिक आय ({fmt_money(actual)}) योजना की सीमा "
                f"({fmt_money(expected)}) से अधिक है। आप वर्तमान में यह आय शर्त पूरी नहीं करते।"
            )
        if op in {"gte", ">="}:
            return (
                f"आपकी वार्षिक पारिवारिक आय ({fmt_money(actual)}) न्यूनतम आवश्यक "
                f"({fmt_money(expected)}) से कम है।"
            )
        return f"आपकी आय ({fmt_money(actual)}) प्रकाशित आय शर्त ({expected}) को पूरा नहीं करती।"
    if rule_type in {"loan_amount", "loan_required"}:
        if op in {"lte", "<="}:
            return (
                f"आपका अनुरोधित ऋण ({fmt_money(actual)}) इस योजना की अधिकतम अनुमति "
                f"({fmt_money(expected)}) से अधिक है।"
            )
        if op in {"gte", ">="}:
            return (
                f"आपका अनुरोधित ऋण ({fmt_money(actual)}) न्यूनतम प्रकाशित राशि "
                f"({fmt_money(expected)}) से कम है।"
            )
        return f"आपकी ऋण राशि ({fmt_money(actual)}) इस योजना की सीमाओं में नहीं आती।"
    if rule_type == "purpose":
        return (
            f"यह योजना '{expected}' उद्देश्य के लिए है, जबकि आपने '{actual}' माँगा है। "
            "उद्देश्य मेल नहीं खाता, इसलिए यह योजना उपयुक्त नहीं है।"
        )
    if rule_type == "category":
        allowed = ", ".join(str(v) for v in (expected if isinstance(expected, list) else [expected]))
        return f"आपकी श्रेणी ({actual}) अनुमत लाभार्थी श्रेणियों ({allowed}) में नहीं है।"
    if rule_type == "gender":
        target = str(expected or "any").lower()
        label = "महिला" if target == "female" else ("पुरुष" if target == "male" else "सभी लिंग")
        return (
            f"यह योजना {label} लाभार्थियों के लिए प्रकाशित है। "
            f"आपका चयनित लिंग ({actual}) मेल नहीं खाता, इसलिए यह योजना आपके लिए उपलब्ध नहीं है।"
        )
    if rule_type == "age":
        return f"आपकी आयु ({actual}) इस योजना की प्रकाशित आयु शर्त को पूरा नहीं करती।"
    if rule_type == "project_type":
        return f"आपका परियोजना प्रकार ({actual}) इस योजना की गतिविधियों से मेल नहीं खाता।"
    return f"आप इस योजना की प्रकाशित '{rule_type}' शर्त को पूरा नहीं करते।"


def matched_suggestion(name: str, score: Any, why_bit: str, timeline: str, lang: str) -> str:
    if lang == "hi":
        return (
            f"सर्वोत्तम मिलान: {name} (स्कोर {score})। "
            f"यह आपके उद्देश्य और पात्रता से सबसे अधिक मेल खाती है।{why_bit} "
            f"योजना समयसीमा: {timeline}। "
            f"अगला कदम: ऊपर विकल्प 1 का विस्तृत अनुभाग देखें, फिर दस्तावेज़ों की पुष्टि और आवेदन के लिए "
            f"अधिकृत चैनल पार्टनर से संपर्क करें।"
        )
    return (
        f"Best match: {name} (score {score}). "
        f"It aligns closest with your purpose and eligibility.{why_bit} "
        f"Scheme timeline: {timeline}. "
        f"Next step: use the detailed section for Option 1 above, then contact the "
        f"authorised channel partner to confirm documents and apply."
    )


def key_matches_prefix(lang: str) -> str:
    return " मुख्य मिलान: " if lang == "hi" else " Key matches: "


def no_match_message(has_near: bool, lang: str) -> str:
    if lang == "hi":
        if has_near:
            return (
                "प्रकाशित पात्रता नियमों के आधार पर कोई योजना आपकी आवश्यकता से मेल नहीं खाती। "
                "नीचे संदर्भ के लिए निकटतम योजना दी गई है, और स्पष्ट कारण बताए गए हैं कि अभी आप इसे क्यों नहीं ले सकते।"
            )
        return "सिस्टम में उपलब्ध प्रकाशित पात्रता नियमों के आधार पर कोई योजना आपकी आवश्यकता से मेल नहीं खाती।"
    if has_near:
        return (
            "No scheme matches your need based on the published eligibility rules. "
            "Below is the closest scheme for reference, with clear reasons why you currently cannot avail it."
        )
    return "No scheme matches your need based on the published eligibility rules available in the system."


def disclaimer_matched(lang: str) -> str:
    if lang == "hi":
        return (
            "जानकारी प्रकाशित स्रोतों से संकलित है और बदल सकती है। "
            "यह प्लेटफ़ॉर्म नवीनतम सफलतापूर्वक सत्यापित जानकारी के आधार पर मार्गदर्शन और योजना मिलान प्रदान करता है। "
            "अंतिम पात्रता, मंजूरी, ब्याज दर, दस्तावेज़ आवश्यकताएँ और वितरण लागू आधिकारिक नियमों "
            "तथा अधिकृत चैनल पार्टनर पर निर्भर हैं।"
        )
    return (
        "Information is compiled from published sources and may change. "
        "The platform provides guidance and scheme matching based on the latest successfully "
        "verified information available to it. Final eligibility, sanction, interest rate, "
        "documentation requirements, and disbursement are subject to the applicable official "
        "rules and the authorized channel partner."
    )


def disclaimer_no_match(lang: str) -> str:
    if lang == "hi":
        return (
            "जानकारी प्रकाशित स्रोतों से संकलित है और बदल सकती है। "
            "निकटतम-योजना सुझाव केवल मार्गदर्शन हैं और इसका अर्थ पात्रता नहीं है।"
        )
    return (
        "Information is compiled from published sources and may change. "
        "Closest-scheme suggestions are guidance only and do not mean you are eligible."
    )


def card_disclaimer(eligible: bool, lang: str) -> str:
    if lang == "hi":
        if eligible:
            return (
                "आप नवीनतम सत्यापित जानकारी के आधार पर प्रकाशित पात्रता मानदंडों को पूरा करते प्रतीत होते हैं। "
                "अंतिम मंजूरी अधिकृत चैनल पार्टनर द्वारा निर्धारित की जाती है।"
            )
        return (
            "यह आपके अनुरोध के निकटतम प्रकाशित योजना है, लेकिन आप वर्तमान में एक या अधिक पात्रता शर्तें पूरी नहीं करते। "
            "यह केवल मार्गदर्शन के लिए दिखाई गई है — उपलब्ध विकल्प के रूप में नहीं।"
        )
    if eligible:
        return (
            "You appear to meet the published eligibility criteria based on the latest verified "
            "information available. Final approval is determined by the authorized channel partner."
        )
    return (
        "This is the closest published scheme to your request, but you currently do not meet "
        "one or more eligibility conditions. It is shown only for guidance — not as an available option."
    )


def emi_unavailable_warning(lang: str) -> str:
    if lang == "hi":
        return "ब्याज दर या अवधि प्रकाशित नहीं है; ईएमआई का अनुमान नहीं लगाया जा सकता।"
    return "Interest rate or tenure not published; EMI cannot be estimated."
