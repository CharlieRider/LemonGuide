---
title: "Evapotranspiration & Crop Coefficients (Kc) for Citrus — Quantifying Water Demand"
year: 2019
source: Agricultural Water Management (citrus ET study) & FAO-56
url: https://www.sciencedirect.com/science/article/abs/pii/S0378377419311643
pdf_url: https://www.fao.org/4/s8376e/s8376e.pdf
pdf_status: downloaded
applicability: citrus general
topics: [watering]
container_relevance: nutrition
pdf_file: s8376e.pdf
---

## Summary
Quantifies how much water a citrus tree actually transpires, expressed as a **crop coefficient (Kc)** applied to reference evapotranspiration (ETo). This is the data layer beneath the ETo×Kc scheduling method already in the repo — the actual numbers that turn a weather-station ETo into a daily water demand.

## Key Findings
- **ETc = ETo × Kc**; citrus Kc is relatively low (canopy is evergreen but conservative), typically **~0.5–0.7** for a mature tree (e.g., orange Kc ≈ **0.55** in midsummer).
- Worked example: ETo 0.25 in/day × Kc 0.55 = **ETc 0.14 in/day** of water demand.
- Measured seasonal citrus actual ET ran roughly **1.7 mm/day (early) → 3.0 mm/day (mid-season) → 1.9 mm/day (late)** in a semi-arid climate.
- Citrus's comparatively low Kc reflects strong stomatal control — it transpires less per unit ground area than many crops, part of why mature citrus tolerates deficit (see the lemon RDI study).
- For containers the orchard Kc must be scaled to **canopy/pot area**, not land area, and a potted tree's exposed wall and faster dry-down raise effective demand beyond the orchard figure.

## Relevance to 19" × 14" Container
Lets you estimate the Lisbon's water need rather than guess: pull daily ETo from CIMIS for coastal LA, multiply by a citrus Kc (~0.5–0.7), and translate to the pot's canopy footprint to size each watering. In practice a 14" west-facing pot in summer will need water roughly daily; the Kc framework explains *why* demand climbs mid-season and eases in the cool months — matching the seasonal feed/water tapering noted elsewhere. Pairs with the CIMIS/ETo×Kc scheduling and water-stress studies.

## Citation
Evapotranspiration, crop coefficients, and physiological responses of citrus trees in semi-arid climatic conditions, 2019. *Agricultural Water Management*. https://www.sciencedirect.com/science/article/abs/pii/S0378377419311643 ; FAO Irrigation & Drainage Paper 24/56, Crop Water Requirements. https://www.fao.org/4/s8376e/s8376e.pdf
