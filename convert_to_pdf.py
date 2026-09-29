import os
import subprocess
import time
import mistune

MD_PATH = r"c:\Users\adity\Desktop\Projects\AROHAN\pramana_government_ui_design_style.md"
HTML_PATH = r"c:\Users\adity\Desktop\Projects\AROHAN\pramana_design_style_temp.html"
PDF_PATH = r"c:\Users\adity\Desktop\Projects\AROHAN\pramana_government_ui_design_style.pdf"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def build_pdf():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    md = mistune.create_markdown(plugins=["table", "task_lists"])
    body_html = md(md_text)

    # Wrap task lists with nice checkboxes if needed
    body_html = body_html.replace('<li>[ ] ', '<li class="task-item"><span class="checkbox"></span> ')
    body_html = body_html.replace('<li>[x] ', '<li class="task-item"><span class="checkbox checked">&#10003;</span> ')

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PRAMANA — Government-Style UI Design System</title>
<style>
  @page {{
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
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
    line-height: 1.55;
    font-size: 10pt;
    margin: 0;
    padding: 0;
    background: #ffffff;
  }}

  /* Top Document Cover Header */
  .doc-header {{
    border-bottom: 2px solid #0b2545;
    padding-bottom: 16px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .doc-header-left {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}

  .doc-logo-svg {{
    width: 48px;
    height: 48px;
  }}

  .doc-header-titles {{
    display: flex;
    flex-direction: column;
  }}

  .doc-main-title {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 19pt;
    font-weight: 800;
    color: #0b2545;
    letter-spacing: 0.02em;
    line-height: 1.15;
  }}

  .doc-sub-title {{
    font-size: 10pt;
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
    font-size: 8.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    text-align: right;
  }}

  /* Typography */
  h1 {{
    font-family: Georgia, 'Times New Roman', serif;
    color: #0b2545;
    font-size: 18pt;
    font-weight: 800;
    border-bottom: 1.5px solid #cbd5e1;
    padding-bottom: 6px;
    margin-top: 20px;
    margin-bottom: 12px;
    break-after: avoid;
  }}

  h2 {{
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #0b2545;
    font-size: 13pt;
    font-weight: 700;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    margin-top: 22px;
    margin-bottom: 10px;
    break-after: avoid;
  }}

  h3 {{
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #12345a;
    font-size: 11pt;
    font-weight: 700;
    margin-top: 16px;
    margin-bottom: 6px;
    break-after: avoid;
  }}

  p {{
    margin: 6px 0 10px 0;
  }}

  /* Blockquote / Legal Notice */
  blockquote {{
    background: #f8fafc;
    border-left: 4px solid #0284c7;
    margin: 14px 0;
    padding: 12px 16px;
    border-radius: 4px;
    color: #1e293b;
    font-size: 9.5pt;
    break-inside: avoid;
  }}

  blockquote strong {{
    color: #0b2545;
  }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0 18px 0;
    font-size: 9pt;
    break-inside: avoid;
  }}

  th {{
    background: #0b2545;
    color: #ffffff;
    font-weight: 600;
    text-align: left;
    padding: 8px 12px;
    border: 1px solid #0b2545;
  }}

  td {{
    padding: 7px 12px;
    border: 1px solid #cbd5e1;
    vertical-align: top;
  }}

  tr:nth-child(even) td {{
    background: #f8fafc;
  }}

  /* Code blocks & inline code */
  code {{
    font-family: Consolas, 'Courier New', monospace;
    font-size: 8.5pt;
    background: #f1f5f9;
    color: #0b2545;
    padding: 2px 5px;
    border-radius: 3px;
    border: 1px solid #e2e8f0;
  }}

  pre {{
    background: #0f172a;
    color: #e2e8f0;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 8.5pt;
    line-height: 1.45;
    margin: 14px 0;
    break-inside: avoid;
  }}

  pre code {{
    background: transparent;
    color: inherit;
    border: 0;
    padding: 0;
  }}

  /* Lists */
  ul, ol {{
    margin: 6px 0 10px 0;
    padding-left: 22px;
  }}

  li {{
    margin-bottom: 4px;
  }}

  li.task-item {{
    list-style: none;
    margin-left: -18px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  span.checkbox {{
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 1.5px solid #64748b;
    border-radius: 3px;
    vertical-align: middle;
  }}

  span.checkbox.checked {{
    background: #0284c7;
    border-color: #0284c7;
    color: #ffffff;
    font-size: 9pt;
    line-height: 14px;
    text-align: center;
  }}

  /* One-line style prompt box */
  .callout-box {{
    background: #e0f2fe;
    border-left: 4px solid #0284c7;
    padding: 12px 16px;
    border-radius: 4px;
    margin-top: 16px;
  }}

  .footer-notice {{
    margin-top: 30px;
    padding-top: 12px;
    border-top: 1px solid #cbd5e1;
    font-size: 8.5pt;
    color: #64748b;
    text-align: center;
    break-inside: avoid;
  }}
</style>
</head>
<body>

<div class="doc-header">
  <div class="doc-header-left">
    <!-- PRAMANA SVG Crest -->
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
      <span class="doc-sub-title">Investigation Review System — UI Design System</span>
    </div>
  </div>
  <div class="doc-badge-pill">
    SIH 2026 Prototype<br>
    <span style="font-size: 7pt; font-weight: normal; color: #78350f;">For Demonstration Only</span>
  </div>
</div>

{body_html}

<div class="footer-notice">
  <strong>PRAMANA · Investigation Review System</strong> · SIH 2026 Prototype · Independent student prototype · Not an official Government of India website
</div>

</body>
</html>"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated HTML at: {HTML_PATH}")

    # Invoke Microsoft Edge headless to print to PDF
    cmd = [
        EDGE_EXE,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_PATH}",
        f"file:///{HTML_PATH.replace(os.sep, '/')}"
    ]

    print("Running Edge print-to-pdf...")
    subprocess.run(cmd, check=True)
    time.sleep(2)

    if os.path.exists(PDF_PATH):
        size = os.path.getsize(PDF_PATH)
        print(f"SUCCESS: Created PDF at {PDF_PATH} ({size:,} bytes)")
    else:
        print("ERROR: PDF was not created.")

    # Remove temporary HTML
    if os.path.exists(HTML_PATH):
        os.remove(HTML_PATH)
        print("Cleaned up temporary HTML.")

if __name__ == "__main__":
    build_pdf()
