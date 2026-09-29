# PRAMANA --- Government-Style UI Design System

A visual design guide for the **PRAMANA Investigation Review System**.
The style is inspired by formal Indian public-sector portals:
restrained, structured, bilingual, accessible, and built around trust
and clarity.

> **Important legal and branding requirement:**
> Under **The State Emblem of India (Prohibition of Improper Use) Act, 2005**, unauthorized reproduction of the State Emblem of India (Ashoka Lion Capital), the "Government of India" / "भारत सरकार" official authority block, or the Digital India insignia is restricted. Unless a team has explicit authorization from the concerned Ministry or Department, student prototypes must not present themselves as authorized Government of India portals.
>
> **Prototype Branding Matrix:**
>
> | Element | Can you use it in your SIH prototype? | Guidance |
> | :--- | :--- | :--- |
> | **Ashoka Lion Capital / State Emblem** | ❌ Avoid unless authorized | Prohibited without statutory authorization. |
> | **“Government of India” with official emblem** | ❌ Avoid unless authorized | Implies official government association. |
> | **Digital India logo** | ❌ Use only with permission | Do not reproduce without explicit license. |
> | **“Government-style” visual design** | ✔️ **Yes** | Navy bars, clean typography, tables, badges. |
> | **Project logo and branding (PRAMANA)** | ✔️ **Yes** | Distinctive project crest (scales of evidence/shield). |
> | **Bilingual interface (English + Hindi)** | ✔️ **Yes** | Standard institutional practice. |
> | **“SIH Prototype — Not an Official Portal”** | ✔️ **Yes (Required)** | Explicit disclaimers in header and footer. |

## 1. Design principles

-   **Institutional, not flashy:** Prefer a calm, official visual
    language over trendy gradients, excessive glassmorphism, or
    decorative animation.
-   **Clarity before density:** Organize complex case information into
    predictable sections, with clear headings and generous spacing.
-   **Evidence and accountability:** Make status, access, provenance,
    audit history, and evidence counts easy to locate.
-   **Bilingual by design:** Support English and Hindi without forcing
    awkward line breaks or cramped controls.
-   **Accessible by default:** Maintain strong contrast, visible
    keyboard focus, readable text, and large enough interaction targets.
-   **Operational honesty:** Clearly distinguish real records from
    synthetic demo data and avoid implying legal authority or official
    approval.

## 2. Overall visual direction

### Look and feel

-   Formal public-sector service portal
-   Deep navy navigation and header bars
-   White and very light blue-grey work surfaces
-   Thin, cool-grey borders
-   Minimal shadows
-   Compact, information-dense tables
-   Simple line icons
-   Clear typography and consistent alignment
-   Small, purposeful use of saffron, green, and blue accents

Avoid: - Neon colors and heavy gradients - Excessive rounded "floating"
cards - Glassmorphism and blurred panels - Oversized decorative
illustrations - Unnecessary motion or animated counters - Using color
alone to communicate status

## 3. Color palette

| Token | Suggested value | Use |
| :--- | :--- | :--- |
| `navy-900` | `#0B2342` | Primary sidebar, main navigation |
| `navy-800` | `#12345A` | Secondary navigation, header accents |
| `blue-700` | `#1457B8` | Primary buttons, links, selected states |
| `blue-100` | `#E8F0FC` | Selected navigation background |
| `page-bg` | `#F3F6F9` | Main application background |
| `surface` | `#FFFFFF` | Cards, tables, dialogs |
| `border` | `#D7E0EA` | Dividers, card outlines, table borders |
| `text-primary` | `#17263B` | Headings and primary content |
| `text-secondary` | `#5F7188` | Supporting text, metadata |
| `success` | `#187847` | Verified or active states |
| `success-bg` | `#EAF6EF` | Success badges |
| `warning` | `#A96600` | Pending review or attention |
| `warning-bg` | `#FFF4D9` | Warning banners and badges |
| `danger` | `#B42318` | Errors or critical states |
| `danger-bg` | `#FDECEB` | Error backgrounds |
| `saffron` | `#E6A100` | Small highlights only |
| `green` | `#16834A` | Small highlights only |

Use accent colors sparingly. The interface should remain predominantly
navy, white, and cool grey.

## 4. Typography

Use a highly legible sans-serif family. Recommended stacks:

-   **English:** `Inter`, `Noto Sans`, `Arial`, sans-serif
-   **Hindi:** `Noto Sans Devanagari`, `Nirmala UI`, sans-serif

Suggested type scale:

| Element | Size | Weight |
| :--- | :--- | :--- |
| Page title | 28–32 px | 700 |
| Section heading | 18–20 px | 600–700 |
| Card title | 15–16 px | 600 |
| Body text | 14–16 px | 400 |
| Table content | 14–15 px | 400–500 |
| Metadata / helper text | 12–14 px | 400 |
| Eyebrow / category label | 11–12 px | 700, uppercase |

Guidelines: - Use sentence case for most labels. - Use uppercase
sparingly for section overlines and metadata. - Keep line-height around
`1.4–1.6` for body text. - Allow Hindi text to wrap naturally; do not
clip or force English-sized line heights if the font needs more room. -
Avoid using letter spacing on long labels or body copy.

## 5. Layout and spacing

### Desktop shell

-   **Top identity header:** approximately `88–104 px` high.
-   **Secondary navigation / breadcrumb bar:** approximately `40–48 px`
    high.
-   **Sidebar:** approximately `240–260 px` wide.
-   **Main content:** fluid width with `28–36 px` padding.
-   **Content max width:** use a generous maximum for very wide screens,
    while allowing case tables to use the available width.

### Spacing scale

Use a consistent 4 px base scale:

`4, 8, 12, 16, 20, 24, 32, 40, 48`

-   Related label and value: `4–8 px`
-   Inside compact controls: `8–12 px`
-   Card padding: `16–24 px`
-   Between sections: `24–32 px`
-   Main page top padding: `24–32 px`

### Corners and elevation

-   Small controls: `4–6 px` radius
-   Cards and panels: `8–10 px` radius
-   Large containers: `10–12 px` radius
-   Use subtle shadows only where they help separate a surface from the
    background.
-   Prefer borders over shadows for tables and administrative panels.

## 6. Header and navigation

### Prototype Identity Header

**Structure:**
1. **Left: PRAMANA Project Brand & Status**
   - Distinctive PRAMANA institutional crest (`PramanaLogo`)
   - Product name: **PRAMANA** with **`SIH Prototype`** badge
   - Hindi title: **`प्रमाण — Investigation Review System`**
   - Statutory disclaimer: **`Independent student prototype · Not an official Government of India website`**
2. **Right: Utility Controls & Prototype Notice**
   - Skip to main content link
   - Text size adjusters (`A-`, `A`, `A+`)
   - Bilingual language selector (`हिंदी |`)
   - Light/Dark theme toggle
   - Role-specific notifications & User profile menu
   - Prototype Pill: **`SIH 2026 Prototype | For Demonstration Only`**

**Institutional Footer:**
- Anchored at the bottom of the application shell.
- Includes full disclaimer: *“SIH 2026 Prototype | For Demonstration Only · Independent student prototype · Not an official Government of India website”*.

### Secondary bar

Use a navy horizontal bar for: - Breadcrumbs - Current section -
Date/time, if operationally necessary

Keep the breadcrumb contrast high and avoid placing essential actions
only in this bar.

### Sidebar

-   Deep navy background
-   Simple line icons
-   Group navigation by task or responsibility
-   Selected item: pale blue background, dark text, and a clear active
    indicator
-   Unselected items: light text with muted secondary labels
-   Include bilingual labels where relevant
-   Keep the help/contact block anchored near the bottom when space
    allows

Do not rely on a thin color strip alone to indicate the selected page;
use background, text weight, and a visible focus/active treatment.

## 7. Page structure

A typical page should follow this hierarchy:

1.  Breadcrumbs
2.  Page title and short explanation
3.  Primary page action, if applicable
4.  Demo/security notice, if applicable
5.  Summary metrics
6.  Search and filters
7.  Main data table or workflow
8.  Pagination and result count
9.  Help or contextual guidance

Keep the title and primary action visually related. On smaller screens,
stack them rather than squeezing them into one row.

## 8. Summary metric cards

Use four cards across on a wide desktop when the content supports it.

Each card contains: - Optional small icon in a lightly tinted square -
Short label - Prominent value - Brief explanatory text

Styling: - White surface - Thin border - Subtle shadow, if needed -
Consistent card height and padding - Large numeric value, around
`28–32 px` - Do not assign a different bright color to every card; use
restrained icon accents

For example: - Cases in scope - Sealed evidence - Cities - Latest
complaint

Metrics should have clear definitions. Avoid implying that a count
represents verified facts if it is only demo data.

## 9. Tables and case lists

Tables are the primary work surface. Optimize them for scanning and
comparison.

### Table anatomy

-   Panel heading with icon, title, and result count
-   Search and filter controls
-   Lightly tinted column header
-   White rows with thin horizontal dividers
-   Pagination and rows-per-page control

### Table styling

-   Header background: `#F1F5F9` or similar
-   Header text: `12 px`, semibold, muted navy
-   Row height: approximately `60–76 px`, depending on bilingual or
    secondary content
-   Horizontal cell padding: `16–20 px`
-   Use tabular numerals for dates, counts, and identifiers
-   Keep column alignment consistent
-   Use a subtle hover state, not a dramatic color change

### Case cell pattern

Show the case identifier as a blue, semibold link. Place the
FIR/reference number below it in smaller muted text.

### Complaint cell pattern

Use: - Complaint title as the primary line - Complainant or secondary
descriptor beneath it

### Location pattern

Show a small location icon, city name, and unit code on separate lines.

### Evidence and access

-   Use compact neutral badges for evidence counts and access roles.
-   Make access level explicit; do not rely on color alone.
-   If evidence integrity is important, expose the relevant verification
    details in the case view or evidence panel.

### Responsive behavior

Do not shrink every column until the table becomes unreadable.
Instead: - Allow horizontal scrolling where appropriate - Keep case ID
and key status visible where feasible - Provide a card/list alternative
on narrow screens - Keep filters usable on mobile

## 10. Role-selection screen

Group role cards under clear responsibility headings, such as: -
Investigating Officers - Intelligence Analyst - Supervisory Officers -
Oversight and Administration

Each role card should include: - Initials or a neutral avatar - Full
name or role label - Job function - Unit / location - A right-facing
chevron indicating navigation

Interaction: - Make the entire card clickable - Use a clear hover state
and visible keyboard focus - Keep the card height consistent within each
group - Use a responsive grid: three columns on wide screens, two on
medium screens, one on narrow screens - Do not communicate role
permissions through avatar color

The role picker should explain that users only see functions permitted
by their role. Role switching should be auditable if the application
requires it.

## 11. Banners, badges, and status

### Synthetic demo banner

Use a pale amber background, fine amber border, small lock or flask
icon, and concise wording.

Example: **Synthetic demo build**\
Isolated database. All people, numbers, and accounts are fictional.

The banner should be visible without overwhelming the page.

### Status badges

Use text plus color: - **Active** --- green - **Under review** ---
amber - **Restricted** --- red - **Archived** --- neutral grey

Ensure the label communicates the state even when viewed without color.

## 12. Buttons, inputs, and controls

### Primary button

-   Blue background
-   White text
-   Medium weight
-   `40–44 px` minimum height
-   Clear hover, pressed, disabled, and focus states

### Secondary button

-   White background
-   Navy text
-   Thin border
-   Used for filters, cancellation, and secondary actions

### Search input

-   White background
-   Light border
-   Search icon on the left
-   Helpful placeholder, such as "Search by case number, complaint, or
    city"
-   Visible focus ring

### Filters

-   Use a labeled button that opens a clear filter panel
-   Show active-filter count or selected values
-   Provide an obvious way to clear filters

### Icon buttons

-   Use only for familiar actions
-   Provide tooltips and accessible labels
-   Ensure a comfortable click/tap target

## 13. Icons and imagery

-   Use one consistent outline icon family, such as Lucide.
-   Prefer simple icons for cases, evidence, location, access, audit,
    settings, and help.
-   Avoid mixing filled, outlined, and 3D icon styles.
-   Avoid decorative stock photography in operational screens.
-   Use official emblems and campaign marks only with authorization.
-   Use a neutral placeholder identity for fictional demo environments.

## 14. Accessibility and usability

Target **WCAG 2.2 AA** as a practical baseline.

-   Ensure text contrast meets the applicable contrast requirements.
-   Support keyboard navigation throughout.
-   Provide a visible focus indicator.
-   Use semantic headings, buttons, links, form labels, and table
    headers.
-   Do not use color as the only status indicator.
-   Support browser zoom and text resizing.
-   Provide meaningful alternative text for informative images.
-   Respect reduced-motion preferences.
-   Ensure controls have sufficiently large interaction targets.
-   Test English and Hindi layouts at realistic text lengths.
-   Announce validation errors and important state changes to assistive
    technology.

## 15. Responsive behavior

### Desktop: 1200 px and above

-   Full sidebar
-   Three- or four-column metric row
-   Three-column role-card grid
-   Full table layout

### Tablet: 768--1199 px

-   Collapsible sidebar
-   Two-column metric cards
-   Two-column role-card grid
-   Table may scroll horizontally

### Mobile: below 768 px

-   Compact header
-   Sidebar becomes a drawer
-   One-column metric and role cards
-   Filters move into a dedicated panel
-   Use a mobile-friendly case list or horizontally scrollable table
-   Keep primary actions easy to reach

## 16. Motion and interaction

Keep motion restrained and functional: - Short transitions, around
`120–180 ms` - Subtle hover and focus transitions - No parallax,
animated backgrounds, or unnecessary page transitions - Respect
reduced-motion settings - Avoid animation that delays access to case
information

## 17. Suggested design tokens

``` css
:root {
  --color-navy-900: #0B2342;
  --color-navy-800: #12345A;
  --color-blue-700: #1457B8;
  --color-blue-100: #E8F0FC;

  --color-page-bg: #F3F6F9;
  --color-surface: #FFFFFF;
  --color-border: #D7E0EA;

  --color-text-primary: #17263B;
  --color-text-secondary: #5F7188;

  --color-success: #187847;
  --color-success-bg: #EAF6EF;
  --color-warning: #A96600;
  --color-warning-bg: #FFF4D9;
  --color-danger: #B42318;
  --color-danger-bg: #FDECEB;

  --radius-control: 6px;
  --radius-card: 9px;
  --radius-panel: 12px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;

  --font-ui: "Inter", "Noto Sans", Arial, sans-serif;
  --font-hindi: "Noto Sans Devanagari", "Nirmala UI", sans-serif;
}
```

## 18. Quality checklist

Before calling the interface ready, verify:

-   [ ] The interface feels formal, calm, and consistent.
-   [ ] The visual hierarchy is clear without relying on oversized
    cards.
-   [ ] Sidebar selection and keyboard focus are obvious.
-   [ ] Tables remain readable with realistic data.
-   [ ] Search, filters, pagination, and actions behave correctly.
-   [ ] Hindi and English labels both fit and remain legible.
-   [ ] Statuses are understandable without color.
-   [ ] Demo data is clearly identified as synthetic.
-   [ ] No unauthorized government emblem, seal, or branding is used.
-   [ ] The interface works at desktop, tablet, and mobile widths.
-   [ ] Empty, loading, error, and permission-denied states are
    designed.
-   [ ] Audit and evidence actions are understandable and traceable.

## One-line style prompt

**Design a restrained, bilingual Indian public-sector investigation
portal: deep navy navigation, white and cool-grey surfaces, formal
sans-serif typography, thin borders, compact data tables, clear
role-based workflows, accessible controls, subtle saffron/green accents,
and explicit synthetic-demo labeling. Prioritize credibility,
traceability, readability, and operational clarity over decoration.**
