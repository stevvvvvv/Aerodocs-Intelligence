"""Génère un petit corpus de démonstration FICTIF (composant, valeurs et références inventés).

Il est conçu pour exercer chaque fonctionnalité de manière contrôlée :
- deux révisions d'un même manuel (gestion des versions, diff) ;
- un bulletin de service en contradiction avec la révision en vigueur (détection de contradictions) ;
- un document « distracteur » sur un autre système (précision de la recherche) ;
- des questions dont la réponse n'existe pas dans le corpus (refus).

Pour les données réelles (EASA), voir scripts/download_easa.py.

Usage : python scripts/make_demo_pdfs.py ../data/demo
"""
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

STYLES = getSampleStyleSheet()
WATERMARK = "FICTITIOUS DEMO DOCUMENT - NOT FOR OPERATIONAL USE"

FILLER = {
    "safety": (
        "Make sure that the safety pins are installed on the landing gear before any task. "
        "Put warning notices in the flight compartment to tell persons not to operate the landing gear controls. "
        "Wear protective goggles and gloves when working with pressurized gas or hydraulic fluid."
    ),
    "jacking": (
        "Lift the aircraft on jacks in accordance with the jacking procedure before the task. "
        "Make sure that the aircraft is in the static ground attitude and that the wheels are clear of the ground. "
        "Clean the external surfaces of the component with a lint-free cloth before the inspection."
    ),
    "records": (
        "Record the task, the measured values and the date in the aircraft maintenance records. "
        "Any value outside the limits given in this section must be reported to the operator engineering department."
    ),
}


def mlg_manual(rev: str) -> list[tuple[str, list[str]]]:
    b = rev == "B"
    seal_fh = "500 FH" if b else "600 FH"
    torque = "90 N.m" if b else "85 N.m"
    content = [
        ("1 GENERAL", [
            "This chapter gives the servicing and inspection data for the main landing gear (MLG) shock strut "
            "of the AD-200 aircraft. The shock strut is an oleo-pneumatic unit filled with hydraulic fluid and dry nitrogen.",
            f"This revision {rev} applies to all AD-200 aircraft in service. " + (
                "Revision B introduces reduced inspection intervals following in-service experience, a new gland nut "
                "torque value and a new corrosion inspection of the lower bearing." if b else
                "This is the initial issue of the chapter."),
            FILLER["safety"],
        ]),
        ("2 SERVICING", [FILLER["jacking"]]),
        ("2.1 Nitrogen charging of the shock strut", [
            "Charge the MLG shock strut with dry nitrogen to a pressure of 1,450 psi at an ambient temperature of 20 °C, "
            "with the shock strut fully extended.",
            "Correct the charging pressure for temperature with the servicing chart: add 4 psi for each degree above 20 °C.",
            "Do not use compressed air or oxygen to charge the shock strut.",
        ]),
        ("2.2 Hydraulic fluid level check", [
            f"Check the hydraulic fluid level of the MLG shock strut every {seal_fh} or 6 months, whichever occurs first.",
            "Use only hydraulic fluid MIL-PRF-5606 for the shock strut servicing.",
            FILLER["records"],
        ]),
        ("PAGEBREAK", []),
        ("3 INSPECTION", [FILLER["safety"]]),
        ("3.1 Chrome surface inspection", [
            "Inspect the exposed chrome surface of the sliding tube for pitting, scratches and corrosion every 12 months.",
            "The maximum permissible pitting depth on the chrome surface is 0.25 mm. Replace the sliding tube if the "
            "pitting depth is more than this limit.",
            FILLER["jacking"],
        ]),
        ("3.2 Dynamic seal inspection", [
            f"Inspect the dynamic seals of the MLG shock strut for hydraulic leakage every {seal_fh}.",
            "The maximum permissible leakage rate at the dynamic seal is 2 drops per minute with the shock strut "
            "compressed. Replace the seals if the leakage rate is more than this limit.",
            FILLER["records"],
        ]),
    ]
    if b:
        content += [
            ("3.3 Lower bearing corrosion inspection", [
                "Inspect the lower bearing of the MLG shock strut for corrosion every 24 months.",
                "Remove light corrosion with abrasive cloth and apply corrosion inhibiting compound. Replace the bearing "
                "if the corrosion depth is more than 0.1 mm.",
            ])
        ]
    content += [
        ("PAGEBREAK", []),
        ("4 TORQUE VALUES", [
            f"Tighten the shock strut gland nut to a torque of {torque}. Safety the gland nut with lockwire after the torque check.",
            "Tighten the torque link attachment bolts to a torque of 120 N.m.",
            FILLER["records"],
        ]),
        ("5 TOOLS AND CONSUMABLES", [
            "Nitrogen charging kit with pressure gauge (accuracy 1 %). Torque wrench 20-200 N.m. "
            "Lint-free cloth. Hydraulic fluid MIL-PRF-5606. Lockwire 0.032 in.",
            FILLER["safety"],
        ]),
    ]
    return content


def service_bulletin() -> list[tuple[str, list[str]]]:
    return [
        ("1 PLANNING INFORMATION", [
            "Subject: Main landing gear - Shock strut dynamic seal - Inspection and replacement.",
            "Reason: Operators reported premature wear of the MLG shock strut dynamic seals on aircraft operated "
            "from short runways with a high number of landings.",
            "Compliance: Recommended. This service bulletin applies to all AD-200 aircraft in service.",
        ]),
        ("2 ACCOMPLISHMENT INSTRUCTIONS", [FILLER["jacking"]]),
        ("2.1 Repetitive inspection", [
            "Inspect the dynamic seals of the MLG shock strut for hydraulic leakage every 400 FH until the new seal "
            "kit is installed.",
            "If the leakage rate is more than 2 drops per minute, replace the dynamic seals before further flight.",
        ]),
        ("2.2 Seal replacement", [
            "Replace the dynamic seals with the improved seal kit P/N 32-1175-02. After installation of the improved "
            "seal kit, the repetitive inspection of paragraph 2.1 is no longer necessary.",
            "Tighten the shock strut gland nut to a torque of 90 N.m after the seal replacement.",
            FILLER["records"],
        ]),
        ("PAGEBREAK", []),
        ("3 MATERIAL INFORMATION", [
            "Seal kit P/N 32-1175-02 contains one dynamic seal, two backup rings and one wiper ring. "
            "Estimated labour: 6 man-hours per shock strut.",
            FILLER["safety"],
        ]),
    ]


def hydraulic_manual() -> list[tuple[str, list[str]]]:
    return [
        ("1 GENERAL", [
            "This chapter gives the maintenance data for the green hydraulic system of the AD-200 aircraft: "
            "engine driven pump (EDP), reservoir, filters and fluid.",
            FILLER["safety"],
        ]),
        ("2 FILTERS", [
            "Replace the EDP case drain filter element every 1,000 FH.",
            "Replace the high pressure filter element when the differential pressure indicator is extended, "
            "or every 3,000 FH, whichever occurs first.",
            FILLER["records"],
        ]),
        ("PAGEBREAK", []),
        ("3 RESERVOIR", [
            "The hydraulic reservoir is pressurized with bleed air to 50 psi.",
            "Check the reservoir fluid level on the level indicator every 7 days.",
        ]),
        ("4 FLUID SAMPLING", [
            "Take a sample of hydraulic fluid from the reservoir every 6 months for contamination analysis.",
            "The maximum permissible water content of the hydraulic fluid is 0.1 %.",
            FILLER["records"],
        ]),
    ]


def build(path: Path, title: str, ref: str, content: list[tuple[str, list[str]]]) -> None:
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(40, A4[1] - 30, f"{ref} - {title}")
        canvas.drawString(40, 25, WATERMARK)
        canvas.drawRightString(A4[0] - 40, 25, f"Page {doc.page}")
        canvas.restoreState()

    story = [Paragraph(title, STYLES["Title"]), Paragraph(ref, STYLES["Normal"]), Spacer(1, 12)]
    for heading, paragraphs in content:
        if heading == "PAGEBREAK":
            story.append(PageBreak())
            continue
        story.append(Paragraph(heading, STYLES["Heading2" if heading.count(".") == 0 else "Heading3"]))
        story += [Paragraph(p, STYLES["BodyText"]) for p in paragraphs]
        story.append(Spacer(1, 6))
    SimpleDocTemplate(str(path), pagesize=A4, title=title).build(story, onFirstPage=on_page, onLaterPages=on_page)


DOCS = [
    ("AMM-32-11_RevA.pdf", "AMM 32-11 - Main Landing Gear Shock Strut", "AD-200 AMM 32-11 Rev. A - 15 Jan 2024", mlg_manual("A")),
    ("AMM-32-11_RevB.pdf", "AMM 32-11 - Main Landing Gear Shock Strut", "AD-200 AMM 32-11 Rev. B - 01 Mar 2025", mlg_manual("B")),
    ("SB-32-014.pdf", "SB 32-014 - MLG Shock Strut Dynamic Seal", "AD-200 Service Bulletin 32-014 - 10 Jun 2025", service_bulletin()),
    ("AMM-29-10_RevC.pdf", "AMM 29-10 - Green Hydraulic System", "AD-200 AMM 29-10 Rev. C - 01 Sep 2024", hydraulic_manual()),
]

# Métadonnées d'import (utilisées par scripts/seed_demo.py et scripts/evaluate.py)
MANIFEST = [
    {"file": "AMM-32-11_RevA.pdf", "family": "AMM 32-11 MLG Shock Strut", "version_label": "Rev. A", "effective_date": "2024-01-15", "title": "AMM 32-11 - MLG Shock Strut"},
    {"file": "AMM-32-11_RevB.pdf", "family": "AMM 32-11 MLG Shock Strut", "version_label": "Rev. B", "effective_date": "2025-03-01", "title": "AMM 32-11 - MLG Shock Strut"},
    {"file": "SB-32-014.pdf", "family": "SB 32-014 Dynamic Seal", "version_label": "Original issue", "effective_date": "2025-06-10", "title": "SB 32-014 - MLG Shock Strut Dynamic Seal"},
    {"file": "AMM-29-10_RevC.pdf", "family": "AMM 29-10 Green Hydraulic System", "version_label": "Rev. C", "effective_date": "2024-09-01", "title": "AMM 29-10 - Green Hydraulic System"},
]

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/demo")
    out.mkdir(parents=True, exist_ok=True)
    for fname, title, ref, content in DOCS:
        build(out / fname, title, ref, content)
        print("écrit", out / fname)
