# Ferrari NLA Pipeline

Pipeline and working environment for the Ferrari NLA illustrated parts catalogue.

The public application lives in:

```text
/var/www/ferrari-nla
```

The processing pipeline lives in:

```text
/var/www/ferrari-nla-pipeline
```

The pipeline operates directly against the site's canonical image and data stores through symlinks. There are no duplicate production copies of catalogue images or JSON inside the pipeline.

For the full product and data architecture, see:

```text
SPECIFICATION.md
```

---

## Installation

```bash
./INSTALL.sh
```

## Directory Layout

```text
/var/www/ferrari-nla-pipeline/
├── data -> /var/www/ferrari-nla/wp-content/uploads/data
├── images -> /var/www/ferrari-nla/wp-content/uploads/images
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

The two symlinks are intentional:

```text
data
    -> /var/www/ferrari-nla/wp-content/uploads/data

images
    -> /var/www/ferrari-nla/wp-content/uploads/images
```

The website therefore contains the canonical catalogue assets.

The pipeline processes them without maintaining a second production copy.

---

# Architecture

The system has three conceptual layers:

```text
SOURCE / HARVEST
      ↓
ENRICHMENT PIPELINE
      ↓
CANONICAL WEBSITE DATA
      ↓
RUNTIME VIEWER
```

More specifically:

```text
external catalogue sources
        ↓
harvest / import
        ↓
diagram images
        ↓
callout detection
        ↓
OCR
        ↓
callout coordinates
        ↓
Ferrari part mapping
        ↓
canonical parts data
        ↓
interactive website
```

The runtime website does not perform OCR or callout detection.

Those are offline enrichment operations.

---

# Canonical Assets

The public website is the authoritative store for current catalogue images and prototype JSON.

## Images

Canonical hierarchy:

```text
images/{maker}/{maker-model}/{submodel}/
```

Ferrari 360 Modena:

```text
images/ferrari/ferrari-360/360-modena/
```

Example:

```text
images/ferrari/ferrari-360/360-modena/360-modena-002.jpg
```

Physical path:

```text
/var/www/ferrari-nla/wp-content/uploads/images/ferrari/ferrari-360/360-modena/360-modena-002.jpg
```

Public URL:

```text
https://ferrari-nla.com/wp-content/uploads/images/ferrari/ferrari-360/360-modena/360-modena-002.jpg
```

---

## Data

Canonical hierarchy:

```text
data/{maker}/{maker-model}/{submodel}/
```

Ferrari 360 Modena:

```text
data/ferrari/ferrari-360/360-modena/
```

Current prototype database:

```text
data/ferrari/ferrari-360/360-modena/parts.json
```

Physical path:

```text
/var/www/ferrari-nla/wp-content/uploads/data/ferrari/ferrari-360/360-modena/parts.json
```

During the prototype phase, `parts.json` acts as the single convenient data source for the viewer.

Long term this data will move into the database.

---

# Naming Convention

There is one naming convention for paths, directories and filenames controlled by this project.

Use:

```text
lowercase
ASCII
hyphen-separated tokens
```

Do not use underscores in canonical project filenames or paths.

Correct:

```text
ferrari-360
360-modena
360-modena-001.jpg
360-modena-001-targets.json
ferrari-paddleocr.py
```

Do not introduce alternative forms such as mixed hyphen and underscore naming.

External source systems may use their own filenames.

For example, a source asset may be:

```text
360-modena_001.jpg
```

but once incorporated into the NLA Global catalogue it becomes:

```text
360-modena-001.jpg
```

The external source name does not determine the canonical project name.

---

# Catalogue Path Is Taxonomy

The directory hierarchy is deliberately meaningful.

For example:

```text
ferrari/ferrari-360/360-modena/
```

means:

```text
maker     Ferrari
model     Ferrari 360
submodel  360 Modena
```

The filesystem therefore contributes directly to the catalogue index.

The same hierarchy should be used consistently for:

```text
images
data
future generated assets
future APIs
catalogue URLs
```

---

# Diagram Images

Diagram images remain raw source diagrams.

The application does not permanently paint:

- availability colours
- selections
- callout highlights
- supplier information
- status indicators

onto the image.

Interactive state is rendered dynamically as browser overlays.

The image is the interface, but the image itself remains clean.

---

# Diagram Numbering

Ferrparts diagram numbering is currently used as the canonical diagram sequence.

Examples:

```text
360-modena-000a.jpg
360-modena-000b.jpg
360-modena-000c.jpg
360-modena-001.jpg
360-modena-002.jpg
...
360-modena-059.jpg
360-modena-100.jpg
...
360-modena-143.jpg
```

The Ferrari 360 Modena corpus contains 106 canonical diagram entries.

A zero-byte diagram file is permitted where a source diagram does not actually exist.

This is preferable to importing a third-party "diagram coming soon" placeholder.

The pathname remains useful to preserve the catalogue sequence even when no useful diagram is available.

---

# The `work` Directory

```text
/var/www/ferrari-nla-pipeline/work/
```

is disposable processing space.

It is not a canonical data store.

Current structure:

```text
work/
├── candidates/
├── crops/
├── debug/
└── output/
```

Typical uses:

### `candidates/`

Intermediate callout candidates generated by geometry detection.

### `crops/`

OCR input crops and other temporary image fragments.

### `debug/`

Annotated diagrams, histograms, overlays and diagnostic output.

### `output/`

Intermediate pipeline results awaiting validation or incorporation into canonical data.

Anything under `work/` should be reproducible.

Important data must eventually be incorporated into the canonical website data or database.

---

# Current Working Target Data

During detector development there may temporarily be files such as:

```text
work/360-modena-001-targets.json
```

These are intermediate enrichment results.

They are not intended to become a second catalogue database.

The target state is for authoritative callout coordinates to be incorporated into:

```text
data/ferrari/ferrari-360/360-modena/parts.json
```

and later into the relational database.

---

# Callout Detection

Callout detection is an offline pipeline process.

Current flow:

```text
diagram
    ↓
geometry candidate detection
    ↓
candidate trimming
    ↓
OCR
    ↓
callout number
    ↓
bounding rectangle
```

Coordinates are stored as source-image pixels:

```json
{
  "callout": "38",
  "x": 412,
  "y": 237,
  "w": 20,
  "h": 15
}
```

Do not normalise coordinates before storage.

The browser can calculate scale directly from:

```text
displayed image size
÷
natural image size
```

---

# OCR

Current OCR uses PaddleOCR recognition.

OCR runs against prepared callout crops produced by the detector.

OCR is an enrichment operation only.

The website runtime does not contain OCR logic.

The runtime consumes already validated:

```text
callout
x
y
w
h
```

data.

---

# Manual Corrections

Detector output is not sacred.

The authoritative interaction map may contain coordinates originating from:

```text
geometry detection
OCR
manual correction
future recognisers
```

Once validated, the origin of a particular rectangle is irrelevant to the viewer.

A missed callout should therefore be corrected in canonical data rather than creating special runtime behaviour.

---

# Ferrari Part Number

The Ferrari OEM part number is the canonical Ferrari part identifier.

Core relationship:

```text
diagram
    ↓
callout
    ↓
Ferrari part number
```

The same Ferrari part number may appear:

- in multiple diagrams
- on multiple submodels
- on multiple Ferrari models

The Ferrari part number therefore anchors the broader parts and supplier graph.

---

# Runtime Status Display

The diagram viewer overlays status information on live callout nodes.

There are two independent status channels.

## Ferrari status

Node centre:

```text
Green   Available
Orange  Special Order
Red     NLA
```

This describes Ferrari supply status only.

## NLA Global status

Node border:

```text
Grey    Unknown
Green   Can Get
Blue    Selected
```

This describes NLA Global or current job state.

A particularly important combination is:

```text
Red centre
Green border
```

meaning:

```text
Ferrari NLA
NLA Global can supply
```

---

# Pipeline Programs

## `ferrari-paddleocr.py`

Current Ferrari diagram callout detection and OCR pipeline.

Responsible for producing positional callout data from raw diagrams.

---

## `eurospares-ferrari-catalogue-4phase.py`

Eurospares catalogue extraction pipeline.

Used for gathering catalogue and Ferrari part information.

---

## `eurospares-ferrari-catalogue-4phase-playwright.py`

Browser-driven variant of the Eurospares catalogue extraction pipeline.

Used where rendered/browser behaviour is required.

---

## `watermark-find.py`

Diagnostic tooling for identifying common image structure across diagram sets.

---

## `watermark-remove.py`

Image-processing utility retained for source image investigation and preparation.

Canonical diagrams should not be destructively modified merely for presentation purposes.

---

## `retry.sh`

Retry/helper script used by catalogue extraction workflows.

---

# Data Ownership Rules

## Canonical

These are authoritative:

```text
/var/www/ferrari-nla/wp-content/uploads/images/
/var/www/ferrari-nla/wp-content/uploads/data/
```

The pipeline sees them through:

```text
/var/www/ferrari-nla-pipeline/images
/var/www/ferrari-nla-pipeline/data
```

## Disposable

This is temporary:

```text
/var/www/ferrari-nla-pipeline/work/
```

## Code

Pipeline code lives directly in:

```text
/var/www/ferrari-nla-pipeline/
```

There should not be a second hidden archive of old experimental scripts.

Version control should provide history.

---

# Operational Rules

1. Do not create duplicate production image trees inside the pipeline.

2. Do not create duplicate production JSON trees inside the pipeline.

3. Do not use underscores in filenames or directories controlled by this project.

4. Do not permanently annotate canonical diagram images.

5. Do not make runtime code dependent on OCR or detector internals.

6. Do not treat `work/` as authoritative storage.

7. Do not retain historical experiments merely because they once existed.

8. Validate useful enrichment output, then move it into canonical data.

9. Keep external source nomenclature separate from canonical NLA Global nomenclature.

10. Prefer one obvious location for every important thing.

---

# Current Ferrari 360 Modena Layout

Images:

```text
/var/www/ferrari-nla-pipeline/images/ferrari/ferrari-360/360-modena/
```

which resolves to:

```text
/var/www/ferrari-nla/wp-content/uploads/images/ferrari/ferrari-360/360-modena/
```

Data:

```text
/var/www/ferrari-nla-pipeline/data/ferrari/ferrari-360/360-modena/parts.json
```

which resolves to:

```text
/var/www/ferrari-nla/wp-content/uploads/data/ferrari/ferrari-360/360-modena/parts.json
```

---

# Design Principle

The essential catalogue relationship is:

```text
IMAGE
  ↓
CALLOUT
  ↓
FERRARI PART NUMBER
  ↓
SUPPLY GRAPH
  ↓
JOB
```

The image is the interface.

The filesystem describes the catalogue.

The Ferrari part number anchors the parts graph.

The pipeline enriches the data.

The website presents the result.

`parts.json` is currently the convenient prototype database.

The relational database will eventually replace it without changing this fundamental architecture.
