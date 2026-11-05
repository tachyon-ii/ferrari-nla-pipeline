# Ferrari NLA Enrichment Pipeline

## Purpose

This document describes the offline processing pipeline used to turn raw Ferrari exploded diagrams into interactive catalogue data.

The pipeline is responsible for:

```text
raw diagram
    ↓
callout detection
    ↓
callout OCR
    ↓
callout coordinates
    ↓
Ferrari part mapping
    ↓
canonical catalogue data
```

The runtime website does **not** perform image analysis.

The website consumes already-enriched data.

---

# 1. Architectural Boundary

The system is divided into:

```text
PIPELINE
    ↓
CANONICAL DATA
    ↓
RUNTIME VIEWER
```

The pipeline may use:

- geometry detection
- OCR
- manual correction
- source catalogue scraping
- enrichment
- validation

The runtime viewer should know nothing about how a callout was detected.

It only requires:

```text
diagram
callout
x
y
w
h
Ferrari part number
```

plus live database-derived status.

---

# 2. Pipeline Location

Pipeline root:

```text
/var/www/ferrari-nla-pipeline
```

Current structure:

```text
ferrari-nla-pipeline/
├── data -> /var/www/ferrari-nla/wp-content/uploads/data
├── images -> /var/www/ferrari-nla/wp-content/uploads/images
├── docs/
├── work/
│   ├── candidates/
│   ├── crops/
│   ├── debug/
│   └── output/
├── eurospares-ferrari-catalogue-4phase.py
├── eurospares-ferrari-catalogue-4phase-playwright.py
├── ferrari-paddleocr.py
├── watermark-find.py
├── watermark-remove.py
├── retry.sh
├── README.md
└── SPECIFICATION.md
```

---

# 3. Canonical Input Images

Images are stored canonically in the website tree.

For Ferrari 360 Modena:

```text
images/ferrari/ferrari-360/360-modena/
```

Example:

```text
images/ferrari/ferrari-360/360-modena/360-modena-001.jpg
```

Physical path:

```text
/var/www/ferrari-nla/wp-content/uploads/images/ferrari/ferrari-360/360-modena/360-modena-001.jpg
```

Pipeline path through symlink:

```text
/var/www/ferrari-nla-pipeline/images/ferrari/ferrari-360/360-modena/360-modena-001.jpg
```

The canonical image is the raw diagram.

It must not be permanently annotated with:

- colours
- status
- selections
- click regions
- debug boxes

---

# 4. Naming Convention

All project-controlled paths and filenames use:

```text
lowercase
hyphen-separated tokens
```

Example:

```text
360-modena-001.jpg
360-modena-001-targets.json
```

External source systems may use different names.

For example:

```text
360-modena_001.jpg
```

may be a valid upstream filename.

It becomes:

```text
360-modena-001.jpg
```

when incorporated into the canonical NLA Global catalogue.

---

# 5. Current Image Corpus

The Ferrari 360 Modena catalogue contains 106 diagram entries.

They include:

```text
360-modena-000a.jpg
360-modena-000b.jpg
360-modena-000c.jpg
360-modena-001.jpg
...
360-modena-059.jpg
360-modena-100.jpg
...
360-modena-143.jpg
```

Some diagram entries may legitimately be zero-byte placeholders where no useful source diagram exists.

This is preferable to retaining a third-party "diagram coming soon" image.

---

# 6. Main Processing Script

Current OCR/detection pipeline:

```text
ferrari-paddleocr.py
```

Its job is to take a raw diagram and produce:

```text
callout number
bounding rectangle
OCR confidence / result
```

for each detected diagram callout.

---

# 7. Processing Stages

The current process is:

```text
1. load raw image
2. scan for candidate number boxes
3. trim candidates
4. de-duplicate / accumulate candidates
5. produce final tight boxes
6. add OCR/click padding
7. crop callout images
8. OCR crops
9. validate OCR result
10. produce target data
```

The order matters.

In particular:

```text
trim first
then accumulate
```

rather than accumulating oversized candidate boxes first.

---

# 8. Geometry Detection

Callout detection currently uses a geometry-based approach.

The numbered callouts tend to have:

- dark digit content
- white surrounding background
- predictable approximate height
- predictable width ranges

Candidate box heights are approximately:

```text
11 pixels
```

Candidate widths currently include:

```text
5
7
12
14
15
18
19
22
```

A surrounding ring is examined around each candidate.

The current detector concept is:

```text
centre sufficiently dark
AND
surround sufficiently white
```

---

# 9. Current Thresholds

Current established thresholds:

```text
BLACKNESS = 180
WHITENESS = 250
```

These belong to the offline detector only.

They must not appear in:

- WordPress PHP
- viewer JavaScript
- viewer CSS
- runtime rendering code

These values are tuning parameters and may change as the detector is improved.

---

# 10. Candidate Trimming

Detected candidates are trimmed before accumulation.

Current trimming constants are approximately:

```text
TRIM_H = 14
TRIM_WHITE = 220.0
```

The purpose is to tighten each candidate around the actual printed digits before comparing or merging regions.

This reduces:

- overlap
- false duplicate boxes
- excessive white margin
- inconsistent OCR input

---

# 11. Click / OCR Padding

The final tight box is not necessarily the best OCR crop.

The detector therefore adds small padding around the tight region.

Current values:

```text
CLICK_PAD_Y = 2
CLICK_PAD_X = 3
CLICK_PAD_X_NARROW = 4
NARROW_SINGLE_MAX_W = 8
```

Narrow single-digit callouts receive slightly more horizontal padding.

This matters because aggressive trimming can remove antialiased digit edges.

OCR should generally use the padded crop.

---

# 12. OCR Input

OCR is performed on the padded target crop.

Current process:

```text
crop
↓
grayscale
↓
convert to BGR if required by recogniser
↓
recognition batch
```

The pipeline does not perform full-page text detection.

The geometry detector has already located the number.

OCR is therefore used in recognition-only mode.

---

# 13. OCR Engine

Current recogniser:

```text
PaddleOCR TextRecognition
```

Model:

```text
en_PP-OCRv5_mobile_rec
```

Recognition-only mode is used.

This has performed materially better than the previous Tesseract approach.

Tesseract was discarded because it produced plausible same-length misreads such as:

```text
57 → 87
```

which are dangerous because they look valid.

---

# 14. Expected Digit Count

The tight box width gives a useful expected digit count.

Current heuristic:

```text
width <= 8      → 1 digit
width 9..16     → 2 digits
width >= 17     → 3 digits
```

This is useful as a sanity check against OCR.

Example:

```text
box suggests 2 digits
OCR returns 3 digits
```

should be treated as suspicious.

---

# 15. Current Recognition Performance

On the currently detected callouts for diagram 001, PaddleOCR achieved:

```text
84 detected targets
84 OCR matches
0 OCR mismatches
```

Manual visual checking showed that recognition itself was effectively solved for those 84 detected targets.

The current problem is therefore primarily:

```text
DETECTION
```

not OCR.

---

# 16. Known Detection Misses

On:

```text
360-modena-001.jpg
```

at least two known callouts were missed by the geometry detector:

```text
38
49
```

These are the immediate tuning targets.

The goal is to improve detection so that these are captured without materially increasing false positives.

---

# 17. Important Tuning Principle

Do not degrade a detector that already performs well merely to capture two missed examples.

The tuning objective is:

```text
recover missed valid callouts
without exploding candidate count
without reducing OCR reliability
```

The detector should remain conservative.

We should investigate why `38` and `49` fail the current geometry test before changing thresholds globally.

Possible causes include:

```text
slightly darker surrounding ring
digit antialiasing
different box width
nearby linework
candidate trimming interaction
local contrast
candidate overlap/de-duplication
```

The exact cause should be measured, not guessed.

---

# 18. Tuning Workflow

For a missed callout:

```text
38
49
```

the tuning process should be:

```text
1. identify exact pixel rectangle manually
2. measure centre intensity
3. measure surrounding ring intensity
4. compare dimensions against accepted candidates
5. identify which detector condition rejected it
6. alter the smallest relevant rule
7. re-run the full diagram
8. compare:
      true positives
      recovered misses
      false positives
      OCR results
```

Do not change multiple parameters simultaneously unless necessary.

---

# 19. Debug Output

Temporary diagnostic files belong under:

```text
work/debug/
```

Examples:

```text
annotated diagrams
candidate overlays
histograms
scan plots
threshold visualisations
rejection reason maps
```

These are not canonical artefacts.

They may be deleted and regenerated.

---

# 20. Candidate Output

Intermediate candidate data belongs under:

```text
work/candidates/
```

Example:

```text
work/candidates/360-modena-001.json
```

This may include:

```text
candidate coordinates
width
height
centre mean
ring mean
trimmed rectangle
accept/reject reason
```

During tuning, storing rejection reason is particularly useful.

---

# 21. OCR Crops

Temporary OCR crops belong under:

```text
work/crops/
```

Example:

```text
work/crops/360-modena-001/
```

Individual files may be named by candidate or final callout.

For example:

```text
candidate-0042.png
callout-38.png
callout-49.png
```

These are disposable.

---

# 22. Pipeline Output

Validated intermediate pipeline output belongs under:

```text
work/output/
```

Example:

```text
work/output/360-modena-001-targets.json
```

This is still not canonical data.

It is the staging result awaiting validation and merge.

---

# 23. Target Data Shape

A detected callout target should contain at minimum:

```json
{
  "callout": "38",
  "x": 412,
  "y": 237,
  "w": 20,
  "h": 15
}
```

Coordinates are source-image pixel coordinates.

Do not store normalised coordinates.

The browser can scale them dynamically.

---

# 24. Authoritative Interaction Map

The final callout map is not merely OCR output.

It is the authoritative interaction map for the diagram.

It may contain targets obtained from:

```text
geometry detection
OCR
manual correction
future recognition methods
```

Once validated, the runtime does not care where a target came from.

---

# 25. Manual Corrections

A detector miss is an enrichment failure, not a runtime failure.

For example, if `38` and `49` remain missed during detector tuning, they may be inserted manually into the authoritative target data.

This allows:

```text
runtime completeness now
```

while:

```text
detector improvement continues independently
```

Manual correction is acceptable.

Silent omission is not.

---

# 26. Part Mapping

After callout detection and OCR, each callout is mapped to Ferrari catalogue data.

The key relationship is:

```text
diagram
+ callout
    ↓
Ferrari part number
```

This mapping may come from:

- Eurospares catalogue extraction
- Ferrparts catalogue extraction
- other source catalogues
- manual validation

The Ferrari part number is the canonical part identity.

---

# 27. Multiple Parts Per Callout

One callout may map to:

- one Ferrari part
- several possible Ferrari parts
- variant-dependent Ferrari parts

Therefore the pipeline must not assume:

```text
one callout = exactly one Ferrari PN
```

The positional target is independent from the semantic part application.

---

# 28. Canonical Data Destination

During the JSON prototype stage, validated enrichment is ultimately merged into:

```text
data/ferrari/ferrari-360/360-modena/parts.json
```

Physical location:

```text
/var/www/ferrari-nla/wp-content/uploads/data/ferrari/ferrari-360/360-modena/parts.json
```

Pipeline path:

```text
/var/www/ferrari-nla-pipeline/data/ferrari/ferrari-360/360-modena/parts.json
```

---

# 29. Temporary Target JSON

A file such as:

```text
work/360-modena-001-targets.json
```

is only temporary.

It exists because detection and OCR are currently being developed separately from the main prototype JSON.

The intended end state is:

```text
target coordinates
    ↓
merged into parts.json
```

Then the temporary target file may be discarded.

---

# 30. Future MySQL Destination

Once MySQL becomes authoritative, the same pipeline output will map approximately to:

```text
diagrams
diagram_targets
parts
part_applications
```

Example:

```text
diagram
    ↓
diagram_target
    ↓
part_application
    ↓
part
```

See:

```text
docs/JSON-MYSQL.md
```

for the relational mapping.

---

# 31. Source Harvest

The upstream catalogue harvest is separate from OCR.

The pipeline may collect:

```text
source HTML
diagram images
part tables
Ferrari part numbers
descriptions
availability
supplier information
```

The principle is:

```text
harvest first
classify later
```

Acquisition should avoid unnecessary filtering.

Raw source oddities can be investigated after collection.

---

# 32. Source Naming vs Canonical Naming

External assets may use:

```text
360-modena_001.jpg
```

The NLA Global canonical asset uses:

```text
360-modena-001.jpg
```

The pipeline must convert source naming into canonical naming at ingestion.

Do not propagate external naming quirks into the internal catalogue.

---

# 33. Placeholder Handling

Third-party placeholder artwork such as:

```text
DIAGRAM COMING SOON
```

should not become a canonical diagram merely because it is a valid image file.

Where a source diagram does not exist, a zero-byte canonical placeholder is acceptable.

This preserves:

```text
catalogue numbering
path identity
index continuity
```

without publishing misleading third-party placeholder artwork.

---

# 34. Validation

Before enrichment output is accepted, validate:

```text
diagram exists
callout value is plausible
bounding rectangle lies within image
box width and height are plausible
OCR digit count is plausible
callout exists in source catalogue where applicable
part mapping exists or is explicitly unknown
```

Unknown values should remain unknown.

Do not invent mappings to satisfy validation.

---

# 35. Duplicate Handling

The detector may produce overlapping or duplicate candidates.

De-duplication should occur after trimming.

The preferred order is:

```text
candidate
↓
trim
↓
compare
↓
merge / suppress duplicates
```

not:

```text
candidate
↓
merge large boxes
↓
trim later
```

This produces more stable final target rectangles.

---

# 36. Runtime Contract

The viewer should ultimately receive a convenient object containing:

```text
diagram
image
callout
x
y
w
h
part number
description
Ferrari status
NLA Global status
selection state
```

The viewer must not care whether that came from:

```text
static parts.json
```

or later:

```text
MySQL → API
```

The enrichment pipeline exists to supply correct upstream data.

---

# 37. Runtime Overlay

The runtime uses the stored pixel rectangle to place an HTML or SVG node over the printed callout.

Scaling is calculated from:

```text
displayed image size
÷
natural image size
```

Conceptually:

```javascript
scaleX = displayedWidth / naturalWidth;
scaleY = displayedHeight / naturalHeight;
```

then:

```javascript
displayX = x * scaleX;
displayY = y * scaleY;
displayW = w * scaleX;
displayH = h * scaleY;
```

No coordinate normalisation needs to be stored.

---

# 38. Status Is Not Pipeline Geometry

Ferrari and NLA Global supply states are not properties of the detected rectangle.

The pipeline's geometry output should remain concerned with:

```text
diagram
callout
rectangle
```

Supply status is joined later through the part record.

This separation matters because status changes over time while callout position does not.

---

# 39. Selection Is Not Pipeline Data

Selection belongs to:

```text
user
vehicle
job
BOM
```

It is not part of OCR or detection output.

The blue selection border is a runtime state.

---

# 40. Batch Processing

The eventual pipeline should support:

```text
single diagram
single submodel
single model
entire marque
```

Examples:

```text
360-modena-001
360-modena
ferrari-360
ferrari
```

The same detector and enrichment process should operate consistently at all scales.

---

# 41. Idempotence

Where practical, pipeline operations should be repeatable.

Re-running detection should:

- regenerate work data
- not create duplicate canonical records
- not destroy manual corrections silently
- not overwrite validated data without deliberate intent

Once MySQL becomes authoritative, imports should update by natural identity rather than blindly insert duplicates.

---

# 42. Manual Override Protection

As the pipeline matures, manually corrected targets should be distinguishable from raw detector output.

A future target record may include provenance such as:

```json
{
  "callout": "38",
  "x": 412,
  "y": 237,
  "w": 20,
  "h": 15,
  "source": "manual"
}
```

or:

```text
detected
manual
validated
```

This prevents a later detector run from accidentally replacing a known-good correction with a worse result.

---

# 43. Provenance

Useful enrichment metadata may include:

```text
source
method
timestamp
confidence
validated
```

Possible methods:

```text
geometry
ocr
manual
catalogue-import
supplier-confirmed
```

The runtime does not need all of this, but the enrichment system may.

---

# 44. Current Immediate Task

The immediate detector task is:

```text
360-modena-001.jpg
```

Known performance:

```text
84 detected
84 OCR correct
```

Known omissions:

```text
38
49
```

The next tuning cycle should determine why those two callouts fail detection.

The first investigation should measure:

```text
their exact box dimensions
centre mean
ring mean
local contrast
neighbouring line interference
trim result
candidate suppression behaviour
```

against nearby successfully detected two-digit targets.

Only then should the detector thresholds or geometry rules be changed.

---

# 45. Success Criterion for Detector Tuning

For diagram 001, the desired result is:

```text
existing 84 retained
+ callout 38
+ callout 49
```

with:

```text
no material increase in false positives
no regression in OCR accuracy
```

A small number of additional valid callouts discovered during tuning is acceptable.

A large increase in noisy candidates is not.

---

# 46. Broader Success Criterion

The pipeline is successful when a new diagram can move through:

```text
raw image
    ↓
detect
    ↓
OCR
    ↓
validate
    ↓
map to Ferrari part numbers
    ↓
publish canonical data
```

without modifying the runtime viewer.

That is the architectural boundary we want to preserve.

---

# 47. Core Principle

The pipeline discovers structure.

The database stores meaning.

The viewer presents it.

```text
IMAGE
  ↓
CALLOUT
  ↓
COORDINATES
  ↓
FERRARI PART NUMBER
  ↓
SUPPLY GRAPH
  ↓
JOB
```

The detector may evolve.

The OCR engine may evolve.

The data store may move from JSON to MySQL.

The runtime relationship remains the same.
