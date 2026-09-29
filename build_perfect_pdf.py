import os
import re
import subprocess
import time
import mistune

MD_PATH = r"c:\Users\adity\Desktop\Projects\AROHAN\pramana_demo_walkthrough_script.md"
HTML_PATH = r"c:\Users\adity\Desktop\Projects\AROHAN\pramana_walkthrough_perfect.html"
PDF_PATH = r"c:\Users\adity\Desktop\Projects\AROHAN\pramana_demo_walkthrough_script.pdf"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def clean_speech_html(raw_text):
    if not raw_text:
        return ""
    
    # 1. Strip blockquote '>' markers and ignore horizontal rule dividers ('---')
    lines = []
    for line in raw_text.strip().splitlines():
        cleaned = re.sub(r'^\s*>\s?', '', line).strip()
        if cleaned and cleaned != "---" and not cleaned.startswith("---"):
            lines.append(cleaned)
    raw_cleaned = "\n".join(lines).strip()
    
    # 2. Split by blank lines to get distinct paragraphs
    raw_paras = [p.strip() for p in re.split(r'\n\s*\n+', raw_cleaned) if p.strip()]
    
    para_htmls = []
    for p in raw_paras:
        p_lines = [l.strip() for l in p.splitlines() if l.strip() and l.strip() != "---"]
        if not p_lines:
            continue
        
        # Check if list of items
        is_list = all(re.match(r'^(?:[•\-\*]|\d+\.)\s+', l) for l in p_lines) and len(p_lines) > 1
        
        if is_list:
            formatted_items = []
            for l in p_lines:
                item_text = re.sub(r'^(?:[•\-\*]|\d+\.)\s+', '', l).strip()
                item_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item_text)
                item_text = item_text.replace('*', '').strip()
                num_match = re.match(r'^(\d+)\.\s+', l)
                bullet_prefix = f"<strong>({num_match.group(1)})</strong> " if num_match else "• "
                formatted_items.append(f"{bullet_prefix}{item_text}")
            joined_list = " &nbsp;•&nbsp; ".join(formatted_items)
            para_htmls.append(f"<p class=\"speech-compact-list\">{joined_list}</p>")
        else:
            joined = " ".join(p_lines)
            # Convert **bold** to <strong>bold</strong>
            joined = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', joined)
            # Remove single asterisks
            joined = joined.replace('*', '')
            # Clean up double spaces
            joined = re.sub(r'\s+', ' ', joined).strip()
            if joined and joined != "---":
                para_htmls.append(f"<p>{joined}</p>")
            
    return "".join(para_htmls)

def parse_and_build():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into sections based on ## headers
    sections = re.split(r'\n(?=## )', content)
    
    act_parts = []
    closing_part = ""
    qa_part = ""

    for s in sections[1:]:
        if s.startswith("## ACT"):
            act_parts.append(s)
        elif s.startswith("## Concluding"):
            closing_part = s
        elif s.startswith("## Evaluator"):
            qa_part = s

    md = mistune.create_markdown(plugins=["table"])

    # Page 1: Header and Overview
    page1_html = f"""
<div class="page-container page-intro">
  <div class="doc-header">
    <div class="doc-header-left">
      <svg class="doc-logo-svg" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="shield-grad" x1="12" y1="6" x2="52" y2="58" gradientUnits="userSpaceOnUse">
            <stop stop-color="#0B2545"/>
            <stop offset="1" stop-color="#07192F"/>
          </linearGradient>
          <linearGradient id="gold-grad" x1="16" y1="16" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop stop-color="#F59E0B"/>
            <stop offset="0.5" stop-color="#D97706"/>
            <stop offset="1" stop-color="#B45309"/>
          </linearGradient>
        </defs>
        <path d="M32 4L54 12V27C54 43.5 44 54.5 32 60C20 54.5 10 43.5 10 27V12L32 4Z" fill="url(#shield-grad)" stroke="url(#gold-grad)" stroke-width="2.5" stroke-linejoin="round"/>
        <path d="M32 8.5L49.5 15V26.5C49.5 40.5 41 50.5 32 55.5C23 50.5 14.5 40.5 14.5 26.5V15L32 8.5Z" stroke="#1E3A8A" stroke-width="1.2" fill="none" opacity="0.8"/>
        <line x1="32" y1="16" x2="32" y2="46" stroke="#FBBF24" stroke-width="2.5" stroke-linecap="round"/>
        <path d="M20 23.5C24.5 22 39.5 22 44 23.5" stroke="#FBBF24" stroke-width="2.2" stroke-linecap="round"/>
        <polygon points="32,20 35,23.5 32,27 29,23.5" fill="#FBBF24"/>
        <line x1="20" y1="23.5" x2="16" y2="33" stroke="#93C5FD" stroke-width="1.2"/>
        <line x1="20" y1="23.5" x2="24" y2="33" stroke="#93C5FD" stroke-width="1.2"/>
        <path d="M14 33C14 37.5 26 37.5 26 33Z" fill="url(#gold-grad)"/>
        <line x1="44" y1="23.5" x2="40" y2="33" stroke="#93C5FD" stroke-width="1.2"/>
        <line x1="44" y1="23.5" x2="48" y2="33" stroke="#93C5FD" stroke-width="1.2"/>
        <path d="M38 33C38 37.5 50 37.5 50 33Z" fill="url(#gold-grad)"/>
        <path d="M24 46H40L37 49.5H27L24 46Z" fill="#FBBF24"/>
        <line x1="21" y1="52" x2="43" y2="52" stroke="#FBBF24" stroke-width="1.8" stroke-linecap="round"/>
      </svg>
      <div class="doc-header-titles">
        <span class="doc-main-title">PRAMANA (प्रमाण)</span>
        <span class="doc-sub-title">Investigation Review System — Official Demo Walkthrough Script</span>
      </div>
    </div>
    <div class="doc-badge-pill">
      SIH 2026 Prototype<br>
      <span style="font-size: 7.5pt; font-weight: normal; color: #78350f;">For Demonstration Only</span>
    </div>
  </div>

  <div class="meta-strip">
    <div class="meta-item">
      <span class="meta-label">Problem Statement</span>
      <span class="meta-value">Inter-Jurisdictional Cyber Investigation & Intelligence Fusion</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Core Motto</span>
      <span class="meta-value">“The system proposes, the officer decides.” (Strict decision support)</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Duration</span>
      <span class="meta-value">6–8 Minutes Total (Modular 3-Min Fast-Track Available)</span>
    </div>
  </div>

  <div class="card intro-card">
    <div class="card-header-bar navy">
      <span class="card-header-title">0. Quick Prep & Environment Reset</span>
      <span class="card-header-tag">Pre-Flight Check</span>
    </div>
    <div class="card-body">
      <p class="small muted">Ensure backend and frontend are running in isolated demo mode before starting the jury session:</p>
      <div class="terminal-block">
        <div class="term-row"><span class="term-cmd"># Backend Terminal (Python 3.11):</span></div>
        <div class="term-row">.venv/Scripts/python -m pramana.cli demo-reset --preload-all</div>
        <div class="term-row">.venv/Scripts/python -m pramana.cli serve --demo</div>
        <div class="term-row" style="margin-top: 6px;"><span class="term-cmd"># Frontend Terminal (Vite):</span></div>
        <div class="term-row">npm run dev &nbsp;&nbsp;<span class="term-comment"># Launches client at http://localhost:5173</span></div>
      </div>
    </div>
  </div>

  <div class="card pitch-card">
    <div class="card-header-bar royal">
      <span class="card-header-title">🎙️ The 30-Second Opening Pitch (For Presenter)</span>
      <span class="card-header-tag">Opening Speech</span>
    </div>
    <div class="card-body speech-body">
      <p class="speech-quote">
        “Respected Jury, modern cyber syndicates exploit jurisdictional boundaries. In digital arrest scams, money is layered across three cities in under twelve minutes. Today, police units work in silos with manual spreadsheets. Evidence fails in court because investigators cannot prove how funds moved or defend against defense scrutiny.
      </p>
      <p class="speech-quote">
        This is <strong>PRAMANA</strong> (प्रमाण) — an investigation review system built for cross-border cyber probes. It does not replace the investigating officer: <strong>the system proposes, the officer decides</strong>. Every node links to a cryptographically sealed document, every calculation is reproducible offline without a database, and every lead can be stress-tested in Challenge Mode before court.”
      </p>
    </div>
  </div>
</div>
"""

    def render_act(act_raw):
        # Filter out stray markdown horizontal rules
        raw_lines = [l for l in act_raw.strip().split("\n") if l.strip() != "---"]
        title_line = raw_lines[0].replace("## ", "").strip()

        # Split sub-sections
        sub_sections = {}
        curr_sub = None
        curr_lines = []

        for line in raw_lines[1:]:
            if line.startswith("### "):
                if curr_sub:
                    sub_sections[curr_sub] = "\n".join(curr_lines).strip()
                curr_sub = line.replace("### ", "").replace(":", "").strip()
                curr_lines = []
            else:
                curr_lines.append(line)
        if curr_sub:
            sub_sections[curr_sub] = "\n".join(curr_lines).strip()

        # Build Act Card
        click_html = md(sub_sections.get("What to Click", ""))
        narration_html = clean_speech_html(sub_sections.get("Spoken Narration", ""))
        eval_raw = sub_sections.get("What Evaluators See", "")
        eval_html = md(eval_raw) if eval_raw else ""

        act_num_match = re.search(r'ACT\s+(\d+)', title_line)
        act_num = act_num_match.group(1) if act_num_match else ""

        html = f"""
<div class="act-card">
  <div class="act-header">
    <div class="act-title-box">
      <span class="act-pill">ACT {act_num}</span>
      <span class="act-title-text">{title_line.replace(f"ACT {act_num}:", "").strip()}</span>
    </div>
    <span class="act-step-badge">Demonstration Step</span>
  </div>
  <div class="act-body">
    <div class="act-col-click">
      <div class="box-title click-title">🎯 WHAT TO CLICK (Action Sequence)</div>
      <div class="click-content">
        {click_html}
      </div>
    </div>
    <div class="act-col-narration">
      <div class="box-title narration-title">🎙️ SPOKEN NARRATION (Presenter Voiceover)</div>
      <div class="narration-content">
        {narration_html}
      </div>
    </div>
    {f'<div class="act-eval-box"><div class="box-title eval-title">👁️ WHAT EVALUATORS SEE ON SCREEN</div><div class="eval-content">{eval_html}</div></div>' if eval_html else ''}
  </div>
</div>
"""
        return html

    act_pages_html = []
    for i in range(0, len(act_parts), 2):
        pair = act_parts[i:i+2]
        page_html = f'<div class="page-container page-acts">\n'
        for act in pair:
            page_html += render_act(act)
        page_html += '</div>\n'
        act_pages_html.append(page_html)

    # Page 7: Closing & Q&A
    closing_raw = closing_part.replace("## Concluding Statement (30 Seconds)", "").strip()
    closing_html = clean_speech_html(closing_raw)
    
    qa_clean = qa_part.replace("## Evaluator Q&A Cheat Sheet", "").strip()
    qa_clean = "\n".join([l for l in qa_clean.splitlines() if l.strip() != "---"])
    qa_html = md(qa_clean)

    page7_html = f"""
<div class="page-container page-closing">
  <div class="card closing-card">
    <div class="card-header-bar royal">
      <span class="card-header-title">🏁 Concluding Statement (30 Seconds)</span>
      <span class="card-header-tag">Final Summary</span>
    </div>
    <div class="card-body speech-body">
      {closing_html}
    </div>
  </div>

  <div class="card qa-card">
    <div class="card-header-bar navy">
      <span class="card-header-title">🛡️ Evaluator & Jury Q&A Cheat Sheet</span>
      <span class="card-header-tag">Defense Playbook</span>
    </div>
    <div class="card-body qa-table-wrap">
      {qa_html}
    </div>
  </div>
</div>
"""

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PRAMANA — Official Demo Walkthrough Script</title>
<style>
  @page {{
    size: A4;
    margin: 11mm 12mm 13mm 12mm;
    @bottom-left {{
      content: "PRAMANA — Investigation Review System | SIH 2026 Prototype";
      font-size: 8pt;
      font-family: 'Segoe UI', Arial, sans-serif;
      color: #64748b;
    }}
    @bottom-right {{
      content: "Page " counter(page);
      font-size: 8pt;
      font-family: 'Segoe UI', Arial, sans-serif;
      color: #64748b;
    }}
  }}

  * {{
    box-sizing: border-box;
  }}

  body {{
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', 'Inter', Arial, sans-serif;
    color: #17263b;
    line-height: 1.45;
    font-size: 9pt;
    margin: 0;
    padding: 0;
    background: #ffffff;
  }}

  /* Page Break Container */
  .page-container {{
    page-break-after: always;
    break-after: always;
    display: flex;
    flex-direction: column;
  }}

  .page-container:last-child {{
    page-break-after: avoid;
    break-after: avoid;
  }}

  /* Document Header */
  .doc-header {{
    border-bottom: 2px solid #0b2545;
    padding-bottom: 10px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .doc-header-left {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}

  .doc-logo-svg {{
    width: 44px;
    height: 44px;
    flex-shrink: 0;
  }}

  .doc-header-titles {{
    display: flex;
    flex-direction: column;
  }}

  .doc-main-title {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 17pt;
    font-weight: 800;
    color: #0b2545;
    letter-spacing: 0.02em;
    line-height: 1.15;
  }}

  .doc-sub-title {{
    font-size: 9pt;
    font-weight: 600;
    color: #1e3a5f;
    margin-top: 2px;
  }}

  .doc-badge-pill {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 4px;
    background: #fef3c7;
    border: 1px solid #fde68a;
    color: #92400e;
    font-size: 7.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    text-align: right;
    line-height: 1.25;
  }}

  /* Meta Strip */
  .meta-strip {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 14px;
  }}

  .meta-item {{
    display: flex;
    flex-direction: column;
  }}

  .meta-label {{
    font-size: 7.5pt;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  .meta-value {{
    font-size: 8.5pt;
    font-weight: 600;
    color: #0b2545;
    margin-top: 1px;
  }}

  /* Generic Card Styles */
  .card {{
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #ffffff;
    margin-bottom: 14px;
    overflow: hidden;
  }}

  .card-header-bar {{
    padding: 6px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .card-header-bar.navy {{
    background: #0b2545;
    color: #ffffff;
  }}

  .card-header-bar.royal {{
    background: #1e3a8a;
    color: #ffffff;
  }}

  .card-header-title {{
    font-size: 9.5pt;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.01em;
  }}

  .card-header-tag {{
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
    font-size: 7pt;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 3px;
    text-transform: uppercase;
  }}

  .card-body {{
    padding: 10px 12px;
  }}

  /* Terminal Block */
  .terminal-block {{
    background: #0f172a;
    color: #e2e8f0;
    padding: 10px 14px;
    border-radius: 5px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 8pt;
    line-height: 1.4;
    margin-top: 6px;
  }}

  .term-cmd {{
    color: #38bdf8;
    font-weight: bold;
  }}

  .term-comment {{
    color: #94a3b8;
  }}

  /* Speech body */
  .speech-body {{
    background: #f0f7ff;
    padding: 12px 14px;
  }}

  .speech-quote {{
    font-size: 9pt;
    color: #1e3a8a;
    line-height: 1.5;
    font-style: italic;
    margin: 4px 0 8px 0;
  }}

  .speech-quote strong {{
    color: #1d4ed8;
    font-style: normal;
  }}

  /* Act Card Styles */
  .act-card {{
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #ffffff;
    margin-bottom: 12px;
    overflow: hidden;
    break-inside: avoid;
    page-break-inside: avoid;
  }}

  .act-header {{
    background: #0b2545;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .act-title-box {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .act-pill {{
    background: #f59e0b;
    color: #0b2545;
    font-size: 8pt;
    font-weight: 800;
    padding: 2px 7px;
    border-radius: 3px;
  }}

  .act-title-text {{
    font-size: 10pt;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.01em;
  }}

  .act-step-badge {{
    color: #93c5fd;
    font-size: 7.5pt;
    font-weight: 600;
    text-transform: uppercase;
  }}

  .act-body {{
    padding: 9px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}

  .box-title {{
    font-size: 7.5pt;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
  }}

  .click-title {{
    color: #0369a1;
  }}

  .act-col-click {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 7px 10px;
  }}

  .click-content ol, .click-content ul {{
    margin: 2px 0;
    padding-left: 18px;
  }}

  .click-content li {{
    margin-bottom: 3px;
    font-size: 8.5pt;
  }}

  .narration-title {{
    color: #1d4ed8;
  }}

  .act-col-narration {{
    background: #f0f7ff;
    border-left: 3.5px solid #2563eb;
    border-radius: 4px;
    padding: 7px 10px;
  }}

  .narration-content p {{
    margin: 3px 0;
    font-size: 8.5pt;
    color: #1e3a8a;
    line-height: 1.45;
    font-style: italic;
  }}

  .narration-content p.speech-compact-list {{
    margin: 4px 0;
    padding: 4px 8px;
    background: #e0f2fe;
    border-radius: 3px;
    font-size: 8pt;
    line-height: 1.4;
  }}

  .narration-content strong {{
    color: #1d4ed8;
    font-style: normal;
  }}

  .eval-title {{
    color: #7e22ce;
  }}

  .act-eval-box {{
    background: #faf5ff;
    border-left: 3.5px solid #a855f7;
    border-radius: 4px;
    padding: 6px 10px;
  }}

  .eval-content ul {{
    margin: 2px 0;
    padding-left: 18px;
  }}

  .eval-content li {{
    font-size: 8.5pt;
    color: #581c87;
    margin-bottom: 2px;
  }}

  /* Code pills */
  code {{
    font-family: Consolas, 'Courier New', monospace;
    font-size: 8pt;
    background: #f1f5f9;
    color: #0b2545;
    padding: 1px 4px;
    border-radius: 3px;
    border: 1px solid #cbd5e1;
  }}

  /* Q&A Table */
  .qa-table-wrap table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 8.5pt;
  }}

  .qa-table-wrap th {{
    background: #0b2545;
    color: #ffffff;
    padding: 6px 10px;
    text-align: left;
    font-size: 8.5pt;
    border: 1px solid #0b2545;
  }}

  .qa-table-wrap td {{
    padding: 7px 10px;
    border: 1px solid #cbd5e1;
    vertical-align: top;
    line-height: 1.4;
  }}

  .qa-table-wrap tr:nth-child(even) td {{
    background: #f8fafc;
  }}

  .qa-table-wrap td:first-child {{
    font-weight: 700;
    color: #0b2545;
    width: 32%;
  }}

  .qa-table-wrap td:last-child {{
    color: #1e3a8a;
    font-style: italic;
  }}
</style>
</head>
<body>

{page1_html}
{"".join(act_pages_html)}
{page7_html}

</body>
</html>"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"Generated clean structured HTML at: {HTML_PATH}")

    # Invoke Microsoft Edge headless to print to PDF
    cmd = [
        EDGE_EXE,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_PATH}",
        f"file:///{HTML_PATH.replace(os.sep, '/')}"
    ]

    print("Printing PDF via Edge...")
    subprocess.run(cmd, check=True)
    time.sleep(2)

    if os.path.exists(PDF_PATH):
        size = os.path.getsize(PDF_PATH)
        print(f"SUCCESS: Created PDF at {PDF_PATH} ({size:,} bytes)")
    else:
        print("ERROR: PDF was not created.")

if __name__ == "__main__":
    parse_and_build()
