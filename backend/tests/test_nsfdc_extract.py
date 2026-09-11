from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scraper.extractors.nsfdc import extract_nsfdc_schemes, extract_nsfdc_eligibility


SAMPLE = """
1
                Micro Finance Scheme (MFS)
NSFDC provides Micro Credit Finance for units costing up to ₹ 1.40 lakh.
Maximum Loan Limit
NSFDC provides loans up to 90% of the Project Cost with a maximum amount of up to ₹ 1.25 lakh per unit.
Rate of Interest
NSFDC charges 2.5% from the SCAs/CAs, which in turn shall charge 6.5% from the Beneficiaries.
Repayment Period
To be repaid in quarterly instalments within a maximum period of three years from the date of disbursement, including a 3-month moratorium period.

2
                Term Loan
NSFDC provides Term Loans for units costing more than ₹ 1.40 lakh and up to ₹ 50.00 lakh.
Maximum Loan Limit
NSFDC provides term loans up to 90% of the project cost, above ₹ 1.25 lakh and up to ₹ 45 lakh per unit.
Rate of Interest
NSFDC shall charge interest @ 4% from the SCAs / CAs, which in turn shall charge 8% from the beneficiaries.
Repayment Period
Repaid in quarterly instalments within seven years, including a 6-month moratorium.
"""


def test_nsfdc_multi_scheme_extract():
    schemes = extract_nsfdc_schemes(SAMPLE, "https://nsfdc.nic.in/scheme")
    assert len(schemes) >= 2
    names = {s["payload"]["name"] for s in schemes}
    assert any("Micro Finance" in n for n in names)
    mfs = next(s["payload"] for s in schemes if "Micro Finance" in s["payload"]["name"])
    assert mfs["max_loan"] == 125000
    assert mfs["interest_rate"] == 6.5
    assert mfs["tenure"] == 36
    assert mfs["moratorium"] == 3


def test_nsfdc_eligibility_income():
    text = "Credit/Loan-Based Schemes: The annual family income of applicants must not exceed ₹ 5.00 lakh. Scheduled Caste."
    elig = extract_nsfdc_eligibility(text, "https://nsfdc.nic.in/eligibility-requirements")
    assert elig is not None
    assert elig["max_income"] == 500000
    assert elig["beneficiary_requirements"]["categories"] == ["SC"]
