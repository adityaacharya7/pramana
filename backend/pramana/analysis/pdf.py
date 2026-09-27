"""Human-readable handover pack (PDF) for a lead. The JSON bundle is the
reproducible part; this is what an officer reads and files."""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .drafts import DISCLAIMER


def _esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(bundle: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"PRAMANA handover - {bundle['lead']['title']}")
    ss = getSampleStyleSheet()
    h1, h2, body = ss["Title"], ss["Heading2"], ss["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10)
    r = bundle["lead"]["receipt"]
    out = [Paragraph("PRAMANA handover pack", h1),
           Paragraph(f"<b>{_esc(r['title'])}</b> &mdash; {_esc(r['subject']['label'])}", body),
           Paragraph(f"Lead status: {_esc(bundle['lead'].get('status'))} &nbsp; Rule: {_esc(r['rule']['id'])} "
                     f"&nbsp; Cases: {_esc(', '.join(r['cases']))}", small),
           Paragraph(f"Generated {_esc(bundle['generated_at'][:19])}Z by {_esc(bundle['generated_by'])}", small),
           Spacer(1, 6), Paragraph(_esc(DISCLAIMER), small), Spacer(1, 8),
           Paragraph("Observation", h2), Paragraph(_esc(r["observation"]), body),
           Paragraph("Evidence Receipt", h2)]

    rows = [["Record", "File", "Source group"]]
    for s in r["supporting_records"][:60]:
        rows.append([Paragraph(_esc(s.get("label")), small), Paragraph(_esc(s.get("filename")), small),
                     Paragraph(_esc(s.get("source")), small)])
    t = Table(rows, colWidths=[85 * mm, 55 * mm, 38 * mm], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    out += [t, Spacer(1, 4), Paragraph(f"Independent sources: {r['independent_sources']}", small)]

    def bullets(title, items):
        out.append(Paragraph(title, h2))
        for it in items or ["None recorded."]:
            out.append(Paragraph(f"&bull; {_esc(it)}", body))

    w = r["what_could_make_this_wrong"]
    bullets("Unknowns", r["unknowns"])
    bullets("Conflicts and contradictions", w["contradictions"])
    bullets("Ordinary explanation", [w["ordinary_explanation"]])
    bullets("Records that would distinguish", w["records_that_would_distinguish"])
    bullets("Next verification step", [r["next_verification_step"]])

    if bundle.get("drafts"):
        out.append(Paragraph(f"Amount estimates and drafts (method: {_esc(bundle.get('attribution_method'))})", h2))
        rows = [["Account", "Estimate", "Range across methods", "Status"]]
        for d in bundle["drafts"]:
            rows.append([Paragraph(_esc(d.get("label") or d["account_id"]), small), f"Rs {d['amount']:,.2f}",
                         f"Rs {d.get('estimate_min') or 0:,.2f} - {d.get('estimate_max') or 0:,.2f}",
                         _esc(d.get("status"))])
        t = Table(rows, colWidths=[70 * mm, 30 * mm, 50 * mm, 28 * mm], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
        out.append(t)

    out.append(Paragraph("Reproducibility and integrity", h2))
    led = bundle.get("ledger") or {}
    cp = led.get("latest_checkpoint") or {}
    for line in [
        f"Bundle hash: {bundle['bundle_hash']}",
        f"Input snapshot hash: {bundle['input_hash']}",
        f"Software: PRAMANA {bundle['software']['pramana']}, engine {bundle['software']['engine']}, "
        f"MO method {bundle['software']['mo_method']}",
        f"Rule versions: {', '.join(f'{k}' for k in bundle['rule_versions'])}",
        f"Applied operations: {len(bundle['operations'])}",
        f"Audit log head: #{(led.get('head') or {}).get('seq')} {(led.get('head') or {}).get('hash', '')}",
        f"Signed checkpoint: #{cp.get('seq')} {cp.get('head_hash', '')} (key {cp.get('key_fingerprint')})",
        "Re-run: python -m pramana.cli verify-bundle <bundle.json>  (no database needed)",
    ]:
        out.append(Paragraph(_esc(line), small))
    out.append(Paragraph("Evidence manifest", h2))
    for f in bundle["evidence_manifest"]:
        out.append(Paragraph(_esc(f"{f['case_id']}  {f['filename']}  sha256 {f['sha256']}"), small))
    doc.build(out)
    return buf.getvalue()
