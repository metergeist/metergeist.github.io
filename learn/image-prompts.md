# AI Image Generation Prompts for /learn/

These prompts are for generating illustrations where inline SVG diagrams aren't sufficient. Use with an AI image generator (DALL-E, Midjourney, etc.) and save results to `/learn/images/`.

## Style Guide

All images should match the chalkboard aesthetic:
- **Background**: Dark green-gray chalkboard texture (#2a3a2e)
- **Drawing style**: Chalk on blackboard — slightly rough white/cream lines, hand-drawn feel
- **Color palette**: Cream/white chalk for primary lines, yellow chalk for highlights, blue chalk for annotations
- **No photorealism** — these should look like a teacher drew them on a chalkboard

---

## Lesson 3: Lens Design & Manufacturing

### Multi-Element Lens Cross-Sections

**Prompt**: "Technical chalk drawing on a dark green chalkboard showing three lens cross-section diagrams side by side, labeled 'Cooke Triplet', 'Zeiss Tessar', and 'Zeiss Planar'. Each shows the arrangement of glass elements in profile view with light rays passing through. Elements drawn as curved lens shapes in cream chalk, light rays in yellow chalk. Labels in neat chalk handwriting. Educational diagram style, clean and readable."

**Filename**: `lens-formulas.png`
**Used in**: Lesson 3 (03-lens-design-manufacturing.html)
**Notes**: The Triplet has 3 elements (positive-negative-positive). The Tessar has 4 elements in 3 groups (positive-negative-cemented doublet). The Planar has 5-6 elements in a symmetric arrangement.

---

## Lesson 13: Anatomy of a TLR

### TLR Cutaway / Exploded View

**Prompt**: "Detailed chalk drawing on a dark green chalkboard showing a cutaway side view of a twin-lens reflex camera. The viewing path is shown with yellow chalk arrows: light enters the top lens, reflects off a 45-degree mirror, and projects onto a ground glass screen at the top. The taking path is shown with blue chalk arrows: light enters the bottom lens, passes through the shutter, and hits the film plane at the back. Labels in cream chalk identify: viewing lens, taking lens, mirror, ground glass, hood, shutter, film plane, focus knob, film advance. Educational technical illustration style."

**Filename**: `tlr-cutaway.png`
**Used in**: Lesson 13 (13-anatomy-of-a-tlr.html)
**Notes**: This is the most important diagram in the course. It should clearly show both optical paths and all major components.

---

## Lesson 17: Printing

### Darkroom / Enlarger Scene

**Prompt**: "Chalk drawing on a dark green chalkboard depicting a photographic enlarger in use. The enlarger is shown in profile with labeled parts: lamp housing at top, negative carrier in the middle, lens below, and a sheet of photographic paper on the baseboard beneath. Light rays shown in yellow chalk passing down through the negative and lens to project an enlarged image onto the paper. A red safelight glows in the corner. The scene conveys the quiet atmosphere of a darkroom. Labels in cream chalk."

**Filename**: `enlarger-scene.png`
**Used in**: Lesson 17 (17-printing.html)

### Contact Sheet Illustration

**Prompt**: "Chalk drawing on a dark green chalkboard showing a photographic contact sheet — a grid of 12 small square photographs (representing a roll of 6x6 medium format film) printed at actual size on a single sheet of paper. Some frames have red grease pencil marks indicating selected images. Frame numbers visible along the edges. The images are suggested as simple chalk sketches — portraits, landscapes, street scenes. Labels explain 'Contact Sheet — 12 frames from one roll of 120 film'. Cream and yellow chalk on dark green board."

**Filename**: `contact-sheet.png`
**Used in**: Lesson 17 (17-printing.html)

---

## General Notes

- Target resolution: 1200×800px or 1200×600px (wide format works best in the lesson layout)
- Export as PNG with transparency OFF (solid chalkboard background)
- Optimize file size with `pngquant` or similar before deploying
- Place generated images in `/learn/images/` directory
- Reference in HTML as: `<img src="/learn/images/filename.png" alt="descriptive alt text" loading="lazy">`
