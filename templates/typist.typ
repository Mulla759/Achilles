// ============================================================
// Achilles — one-page student resume template (Typst)
//
// Layout follows the standard "Jake's resume" structure used by the reference
// resumes in resume/: centered name, pipe-separated contact line with
// underlined links, ruled small-caps section headings, and two-line entries.
//
// This file contains NO personal data. Everything arrives as JSON through
// `sys.inputs.resume`, so nothing is string-interpolated into Typst source and
// no user text needs escaping — a bullet containing #, $, *, _, @, [ ] or a
// backslash renders literally.
//
//   typst compile --input resume='{"contact":{...}}' typist.typ out.pdf
//
// Single column on purpose: multi-column resumes scramble in most ATS parsers.
//
// `density` (0.0 = roomy .. 1.0 = tightest) is the one-page fitting lever. The
// pipeline compiles at 0, and if the result spills to two pages it re-compiles
// at progressively higher density before it ever asks the model to cut a
// bullet. Squeezing whitespace is free; deleting an accomplishment is not.
//
// ENTRY GEOMETRY differs per section, matching the reference:
//   Education        School (bold)      ......  Location
//                    Degree (italic)    ......  Date
//   Work Experience  Employer (bold)    ......  Date          <- or Title, if
//                    Title (italic)     ......  Location         lead_with="role"
//   Projects         Name (bold) | Stack (italic)  ......  Date
// ============================================================

#let data = json(bytes(sys.inputs.at("resume", default: "{}")))
#let density = float(sys.inputs.at("density", default: "0"))

#let lerp(a, b) = a + (b - a) * density

// Geometry is tuned so a reference-length bullet (~118 characters) sits on one
// line at density 0 — matching resume/PM_Abdullahi_Abdi.pdf. Widening the text
// block is what buys that, so margins tighten before type size does.
#let body-size   = lerp(9.8, 8.6) * 1pt
#let lead        = lerp(0.60, 0.38) * 1em
#let bullet-gap  = lerp(2.4, 1.1) * 1pt
#let entry-gap   = lerp(4.6, 1.8) * 1pt
#let section-gap = lerp(5.6, 2.2) * 1pt
#let side-margin = lerp(0.44, 0.36) * 1in
#let top-margin  = lerp(0.42, 0.28) * 1in

#let ink = rgb("#000000")

#set document(
  title: data.at("contact", default: (:)).at("name", default: "Resume") + " — Resume",
  author: data.at("contact", default: (:)).at("name", default: ""),
)
#set page(paper: "us-letter", margin: (x: side-margin, top: top-margin, bottom: top-margin * 0.9))
#set text(font: ("New Computer Modern", "Latin Modern Roman", "Times New Roman"), size: body-size, fill: ink)
#set par(leading: lead, justify: false)
#show link: it => underline(it)

#let has(dict, key) = {
  let v = dict.at(key, default: "")
  type(v) == str and v.trim() != ""
}
#let get(dict, key) = dict.at(key, default: "").trim()

// ---------------- SECTION HEADING ----------------
// Small-caps-ish heading with a full-width rule beneath, as in the reference.
#let section(title) = {
  v(section-gap)
  block(below: 1.5pt)[
    #text(size: body-size * 1.18, weight: "bold")[#title]
    #v(-4.5pt)
    #line(length: 100%, stroke: 0.7pt + ink)
  ]
}

#let bullets(items) = {
  set list(marker: [•], indent: 6pt, body-indent: 5pt, spacing: bullet-gap)
  list(..items.map(b => [#b]))
}

// Two-line entry: bold/right on top, italic/right underneath.
#let entry2(primary, primary-meta, secondary, secondary-meta, items) = {
  // `below` must stay > 0: at 0pt the following bullet list is extracted onto
  // the same text line as the entry header ("Expected Dec 2027• Coursework..."),
  // and the extracted text is exactly what an ATS parser reads.
  block(above: entry-gap, below: 1.2pt, width: 100%)[
    #grid(
      columns: (1fr, auto),
      align: (left, right),
      text(weight: "bold")[#primary], text[#primary-meta],
    )
    #if secondary != "" or secondary-meta != "" [
      #v(-1pt)
      #grid(
        columns: (1fr, auto),
        align: (left, right),
        text(style: "italic")[#secondary], text(style: "italic")[#secondary-meta],
      )
    ]
  ]
  if items.len() > 0 { bullets(items) }
}

// Single-line entry used by Projects: "Name | Stack" on the left, date right.
#let entry1(name, stack, meta, items) = {
  // `below` must stay > 0: at 0pt the following bullet list is extracted onto
  // the same text line as the entry header ("Expected Dec 2027• Coursework..."),
  // and the extracted text is exactly what an ATS parser reads.
  block(above: entry-gap, below: 1.2pt, width: 100%)[
    #grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: "bold")[#name]
        if stack != "" { text[ | ]; text(style: "italic")[#stack] }
      },
      text[#meta],
    )
  ]
  if items.len() > 0 { bullets(items) }
}

#let items-of(e) = e.at("bullets", default: ())

// ---------------- HEADER ----------------
#let c = data.at("contact", default: (:))
#align(center)[
  #text(size: body-size * 2.05, weight: "bold")[#get(c, "name")]
  #v(2pt)
  #text(size: body-size)[
    #let parts = ()
    #if has(c, "phone")    { parts.push(get(c, "phone")) }
    #if has(c, "email")    { parts.push(link("mailto:" + get(c, "email"))[#get(c, "email")]) }
    #if has(c, "linkedin") { parts.push(link("https://" + get(c, "linkedin"))[#get(c, "linkedin")]) }
    #if has(c, "github")   { parts.push(link("https://" + get(c, "github"))[#get(c, "github")]) }
    #if has(c, "website")  { parts.push(link("https://" + get(c, "website"))[#get(c, "website")]) }
    #parts.join([ | ])
  ]
  #if has(data, "target_role") or has(data, "availability") [
    #v(2pt)
    #text(size: body-size)[
      #get(data, "target_role")
      #if has(data, "availability") [
        #if has(data, "target_role") [ #sym.dot.c ]
        *Availability:* #get(data, "availability")
      ]
    ]
  ]
]

// ---------------- EDUCATION ----------------
// School bold with location right; degree italic with date right.
#let edu = data.at("education", default: ())
#if edu.len() > 0 {
  section(data.at("education_title", default: "Education"))
  for e in edu {
    entry2(get(e, "org"), get(e, "location"), get(e, "role"), get(e, "date"), items-of(e))
  }
}

// ---------------- TECHNICAL SKILLS ----------------
#let sk = data.at("skills", default: ())
#if sk.len() > 0 {
  section(data.at("skills_title", default: "Technical Skills"))
  v(2pt)
  for g in sk {
    block(above: 1.5pt, below: 1.5pt)[
      #text(weight: "bold")[#get(g, "label"):] #get(g, "items")
    ]
  }
}

// ---------------- WORK EXPERIENCE / LEADERSHIP ----------------
#let lead-with = data.at("lead_with", default: "org")
#let role-entry(e) = {
  // Reference layout: employer bold + date right, title italic + location right.
  // lead_with: "role" flips the two left-hand slots for a Jake's-resume ordering.
  let top = if lead-with == "role" { get(e, "role") } else { get(e, "org") }
  let bottom = if lead-with == "role" { get(e, "org") } else { get(e, "role") }
  entry2(top, get(e, "date"), bottom, get(e, "location"), items-of(e))
}

#let exp = data.at("experience", default: ())
#if exp.len() > 0 {
  section(data.at("experience_title", default: "Work Experience"))
  for e in exp { role-entry(e) }
}

// ---------------- PROJECTS ----------------
#let proj = data.at("projects", default: ())
#if proj.len() > 0 {
  section(data.at("projects_title", default: "Projects"))
  for e in proj {
    entry1(get(e, "role"), get(e, "stack"), get(e, "date"), items-of(e))
  }
}

// ---------------- LEADERSHIP & AWARDS ----------------
#let lead-sec = data.at("leadership", default: ())
#if lead-sec.len() > 0 {
  section(data.at("leadership_title", default: "Leadership & Awards"))
  for e in lead-sec { role-entry(e) }
}
