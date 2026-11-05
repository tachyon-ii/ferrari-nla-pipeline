# NLA Global Illustrated Parts Catalogue
## Architecture Specification

## 1. Purpose

Build an interactive illustrated parts catalogue for legacy vehicles in which the **diagram is the primary user interface**.

The system must support:

- marque → model → submodel navigation
- exploded parts diagrams
- clickable diagram callouts
- Ferrari OEM part numbers as canonical Ferrari part identifiers
- Ferrari availability status
- NLA Global availability status
- supplier listings
- part selection
- vehicle-specific job and BOM creation
- future service templates
- future two or three click quoting
- future procurement and parts tracking
- eventual migration from JSON-backed prototype data to a relational database

The immediate implementation may use a **single JSON data file per submodel** as a temporary database so that the interface and data model can be developed rapidly.

The long-term database architecture must not be constrained by the temporary JSON implementation.

---

# 2. Universal Naming Convention

There is one naming grammar for the entire catalogue.

## 2.1 Hard rule

All canonical:

- URLs
- paths
- directory names
- filenames
- slugs
- catalogue identifiers
- derived data filenames
- future API route components

must use:

```text
lowercase
ASCII
hyphen-separated tokens
```

The underscore character is prohibited in canonical catalogue paths and filenames.

There must never be separate naming conventions for filesystem paths, URLs and image files.

## 2.2 Examples

Correct:

```text
ferrari
ferrari-360
360-modena
360-modena-001.jpg
360-modena-002.jpg
360-modena-000a.jpg
360-modena-001-targets.json
```

Incorrect naming styles include mixed separators or abbreviated private naming schemes.

The canonical compound identifier for diagram 001 of a Ferrari 360 Modena is:

```text
360-modena-001
```

---

# 3. Canonical Catalogue Hierarchy

The physical path is part of the catalogue taxonomy.

Use:

```text
images/{maker}/{maker-model}/{submodel}/{diagram-image}
```

For Ferrari 360 Modena:

```text
images/ferrari/ferrari-360/360-modena/
```

Example diagram:

```text
images/ferrari/ferrari-360/360-modena/360-modena-002.jpg
```

Canonical public URL:

```text
https://ferrari-nla.com/wp-content/uploads/images/ferrari/ferrari-360/360-modena/360-modena-002.jpg
```

The hierarchy is:

```text
maker
└── maker-model
    └── submodel
        └── diagram
```

Example:

```text
ferrari
└── ferrari-360
    ├── 360-modena
    ├── 360-spider
    └── 360-challenge-stradale
```

Future examples:

```text
ferrari/
├── ferrari-355/
│   ├── 355-berlinetta/
│   └── 355-spider/
├── ferrari-360/
│   ├── 360-modena/
│   └── 360-spider/
└── ferrari-430/
    ├── 430-coupe/
    └── 430-spider/
```

Equivalent structures can later exist for:

```text
porsche/
lamborghini/
maserati/
aston-martin/
...
```

---

# 4. Path-Derived Catalogue Index

The canonical path itself must contain enough information to construct the basic catalogue tree.

Given:

```text
images/ferrari/ferrari-360/360-modena/
```

the application can infer:

```text
maker    Ferrari
model    Ferrari 360
submodel 360 Modena
```

The filesystem therefore provides the structural catalogue index.

A separate manually maintained taxonomy must not be required merely to discover:

```text
Ferrari
→ Ferrari 360
→ 360 Modena
```

Additional database metadata may later provide:

- display names
- production dates
- chassis ranges
- model notes
- region variants
- transmission variants
- presentation ordering

but these do not replace the canonical path identity.

---

# 5. SEO Principle

Catalogue taxonomy must be reflected directly in public URLs.

A diagram URL therefore contains:

```text
Ferrari
Ferrari 360
360 Modena
diagram identifier
```

Example:

```text
/wp-content/uploads/images/ferrari/ferrari-360/360-modena/360-modena-024.jpg
```

rather than an opaque image address.

The same hierarchy should eventually be reflected in catalogue pages:

```text
/ferrari/
/ferrari/ferrari-360/
/ferrari/ferrari-360/360-modena/
```

The path structure therefore serves both:

1. application navigation
2. human readability
3. search engine understanding
4. deterministic asset location

---

# 6. Raw Diagram Images

The harvested diagram image is the canonical source asset.

Example:

```text
360-modena-001.jpg
```

The source image must remain immutable.

Do not permanently paint onto the source image:

- availability colours
- selection state
- clickable regions
- highlights
- status markers
- hover effects
- annotations

Interactive information is layered over the image dynamically in the browser.

This preserves a clean diagram while allowing the same image to represent different live states.

---

# 7. Diagram Numbering

Ferrparts diagram nomenclature is adopted as the canonical diagram numbering scheme.

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

The diagram identifier is:

```text
000a
000b
000c
001
002
...
143
```

The compound diagram identity is:

```text
{submodel}-{diagram}
```

Example:

```text
360-modena-024
```

---

# 8. Data Hierarchy

Prototype data must mirror the image hierarchy.

Images:

```text
/wp-content/uploads/images/ferrari/ferrari-360/360-modena/
```

Data:

```text
/wp-content/uploads/data/ferrari/ferrari-360/360-modena/
```

Prototype data file:

```text
/wp-content/uploads/data/ferrari/ferrari-360/360-modena/parts.json
```

The overall structure is therefore:

```text
uploads/
├── images/
│   └── ferrari/
│       └── ferrari-360/
│           └── 360-modena/
│               ├── 360-modena-000a.jpg
│               ├── 360-modena-000b.jpg
│               ├── 360-modena-000c.jpg
│               ├── 360-modena-001.jpg
│               ├── 360-modena-002.jpg
│               └── ...
└── data/
    └── ferrari/
        └── ferrari-360/
            └── 360-modena/
                └── parts.json
```

This same hierarchy must be used for every marque.

---

# 9. Prototype JSON Strategy

During the prototype phase, one JSON file acts as the temporary database for the submodel.

For Ferrari 360 Modena:

```text
data/ferrari/ferrari-360/360-modena/parts.json
```

That file contains enough information to drive:

- catalogue navigation
- diagram image selection
- diagram callout positioning
- Ferrari part mapping
- Ferrari supply status
- NLA Global supply status
- supplier listings
- substitutions
- current prototype selection state where required

The purpose is convenience.

We should be able to alter one file and immediately alter the prototype.

The JSON representation is not intended to dictate the eventual database schema.

---

# 10. Prototype JSON Shape

Conceptually:

```json
{
  "maker": "ferrari",
  "model": "ferrari-360",
  "submodel": "360-modena",
  "diagrams": [
    {
      "diagram-number": "001",
      "diagram-title": "Crankcase",
      "image": "/wp-content/uploads/images/ferrari/ferrari-360/360-modena/360-modena-001.jpg",
      "parts": [
        {
          "callout": "38",
          "x": 412,
          "y": 237,
          "w": 20,
          "h": 15,
          "part-number": "123456",
          "description": "Example part",
          "ferrari-status": "nla",
          "nla-status": "available",
          "listings": []
        }
      ]
    }
  ]
}
```

Hyphenated keys are acceptable in JSON because they are explicitly named fields.

This keeps the naming grammar visually consistent with the rest of the system.

---

# 11. Coordinate Storage

Callout coordinates are stored in **source-image pixels**.

Example:

```json
{
  "callout": "38",
  "x": 412,
  "y": 237,
  "w": 20,
  "h": 15
}
```

Do not store normalised coordinate values.

Normalisation is unnecessary because the browser already knows:

```text
display width
source width

display height
source height
```

The scale is calculated at runtime:

```javascript
const scaleX = displayedWidth / naturalWidth;
const scaleY = displayedHeight / naturalHeight;

const displayX = x * scaleX;
const displayY = y * scaleY;
const displayW = w * scaleX;
const displayH = h * scaleY;
```

The stored values therefore remain the exact coordinates generated by the detector.

---

# 12. Callout Detection Pipeline

Callout positions are generated offline.

The processing pipeline is:

```text
raw diagram
    ↓
geometry detection
    ↓
candidate callout boxes
    ↓
trim
    ↓
OCR
    ↓
callout number
    ↓
position
    ↓
Ferrari callout mapping
    ↓
Ferrari part number
```

The established detector currently uses approximately:

```text
blackness threshold = 180
whiteness threshold = 250
```

These thresholds belong exclusively to the offline enrichment process.

They must not appear in:

- WordPress PHP
- viewer JavaScript
- viewer CSS
- runtime rendering logic

The runtime only consumes the resulting data.

---

# 13. Detection Output Is Enrichment Data

The viewer must not care how a callout coordinate was obtained.

Possible sources include:

```text
geometry detector
OCR
template recognition
manual correction
future machine learning
```

All produce the same authoritative result:

```text
diagram
+ callout
+ rectangle
```

Therefore a detection miss such as callout `38` or `49` is corrected in the canonical data without requiring any viewer change.

Detector improvement and viewer behaviour remain separate concerns.

---

# 14. Canonical Ferrari Part Identity

The Ferrari OEM part number is the canonical Ferrari part identifier.

The core relationship is:

```text
diagram
    ↓
callout
    ↓
Ferrari part number
```

A callout may resolve to:

- one Ferrari part number
- multiple Ferrari part numbers
- variant-dependent Ferrari part numbers

The same Ferrari part number may occur:

- on several diagrams
- on several submodels
- on several Ferrari models
- in several service templates

Therefore the Ferrari part number does not belong exclusively to any individual diagram.

---

# 15. Diagram Callouts Are Spatial References

A callout is not itself the part.

It is a spatial reference on a particular diagram.

Conceptually:

```text
diagram
+ callout
+ rectangle
    ↓
part application
    ↓
Ferrari part number
```

This distinction becomes important once the same Ferrari part appears in multiple diagrams and vehicles.

---

# 16. Interactive Overlay Architecture

The raw diagram is displayed normally.

Interactive nodes are positioned over the numbered callouts using the stored coordinate rectangles.

Conceptually:

```text
raw diagram
     +
callout position data
     ↓
interactive diagram
```

Each overlay node is a normal browser element positioned over the corresponding printed number.

The overlay provides:

- click target
- hover state
- Ferrari availability colour
- NLA Global status border
- selection state
- future tooltip behaviour

No alternate image generation is required.

---

# 17. Live Node Principle

The overlay must make it immediately apparent that a numbered callout is **live**.

A user looking at the diagram should be able to identify interactable numbered nodes without consulting the right-hand parts tree.

Hovering a node should provide visible feedback.

Clicking a node opens the corresponding Ferrari part.

The image therefore becomes the primary parts interface rather than merely illustrating a separate catalogue.

---

# 18. Two Independent Status Channels

Each live node communicates two independent status dimensions.

They must not be conflated.

---

# 19. Ferrari Status

The **centre or fill** of the node represents Ferrari's own supply status.

Three states:

```text
Green   Available
Orange  Special Order
Red     NLA
```

These colours describe **Ferrari only**.

They do not describe NLA Global availability.

---

# 20. NLA Global Status

The **surrounding border** represents NLA Global status.

Three operational states are required:

```text
Grey    Unknown
Green   Can Get
Blue    Selected
```

We deliberately do not currently need separate:

```text
Orange  Can Order
Red     Cannot Get
```

because:

- anything we can reliably order counts as `Can Get`
- anything we cannot presently supply remains `Unknown`
- we do not need to assert permanent inability to obtain a part

Selection overrides the normal NLA Global border display with blue.

---

# 21. Combined Node Meaning

The two colour channels communicate two facts simultaneously.

## Ferrari available and NLA Global can supply

```text
green centre
green border
```

## Ferrari special order and NLA Global can supply

```text
orange centre
green border
```

## Ferrari NLA but NLA Global can supply

```text
red centre
green border
```

This is one of the most important states in the product.

It visually communicates:

> Ferrari cannot supply this part. NLA Global can.

## Ferrari NLA and no validated NLA Global source yet

```text
red centre
grey border
```

This represents an unresolved supply problem.

It also becomes valuable demand intelligence for aftermarket development.

## Selected part

```text
any Ferrari centre
blue border
```

The Ferrari state remains visible while the selection state is shown independently.

---

# 22. Status Legend

The viewer requires a permanent compact legend explaining the two channels.

Use two rows of three states.

Conceptually:

```text
Ferrari      ● Available      ● Special Order      ● NLA
NLA Global   ○ Unknown        ○ Can Get            ○ Selected
```

The first row explains the node fill.

The second row explains the surrounding border.

The legend should be visible while using the diagram.

---

# 23. Toolbar Layout

The magnifier and fullscreen controls must not sit over the diagram itself.

They should move into the grey surround above the drawing.

The toolbar becomes approximately:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Ferrari      ● Available   ● Special Order   ● NLA          🔍   ⛶ │
│ NLA Global   ○ Unknown     ○ Can Get         ○ Selected             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                              DIAGRAM                                 │
│                                                                      │
```

Legend:

```text
left
```

Viewer controls:

```text
right
```

This avoids obscuring diagram content and removes any requirement to analyse each image to determine where a legend might fit.

---

# 24. Callout Interaction

Clicking a callout follows:

```text
callout
    ↓
Ferrari part number
    ↓
part modal
```

The modal can display:

- Ferrari part number
- description
- diagram
- callout number
- Ferrari status
- NLA Global status
- supplier listings
- current price information
- substitutions
- supersessions
- quantity
- future default quantity
- selected state
- future job inclusion

---

# 25. Selection

Selection is not a supply status.

It is a user or job state.

Conceptually:

```text
user
→ vehicle
→ job
→ required part
```

For the prototype, the existing wishlist mechanism may continue acting as temporary selection storage.

Long term, `Selected` means that the part has been added to a vehicle-specific job or BOM.

Its display state is:

```text
blue surrounding border
```

---

# 26. Quantity

Default quantity is associated with the part application rather than blindly with the Ferrari part number globally.

Examples include:

```text
spark plug       8 per vehicle
knock sensor     4 per vehicle
hose             2 per vehicle
left component   1 per side
```

The future enrichment process may derive these defaults from:

- diagram application
- vehicle model
- engine
- Ferrari catalogue data
- LLM batch enrichment
- verified service templates

The mechanic may always override the default quantity.

---

# 27. Ferrari Status and NLA Global Status Are Database Data

Coordinate information belongs to the diagram callout relationship.

Supply information does not.

Conceptually:

```text
diagram target
    diagram
    callout
    x
    y
    width
    height
```

joins to:

```text
Ferrari part
    part number
    description
    Ferrari availability
```

which joins to:

```text
supplier offers
NLA Global availability
aftermarket alternatives
supersessions
replacement components
```

The prototype JSON may flatten these relationships into a single convenient object.

The eventual database must separate them correctly.

---

# 28. Supplier Graph

The Ferrari part number anchors supplier resolution.

Conceptually:

```text
Ferrari part number
    ↓
Ferrari OEM
    ↓
independent OEM
    ↓
aftermarket
    ↓
NOS
    ↓
used
    ↓
remanufactured
    ↓
repair component
```

Supplier products may map to:

- one Ferrari part number
- several Ferrari part numbers
- complete kits
- subcomponents of a Ferrari assembly

The supply model must therefore support many-to-many relationships.

---

# 29. Repair Components

Not every useful aftermarket component has a Ferrari part number.

A Ferrari assembly may contain an unlisted service component such as:

- seal
- O-ring
- diaphragm
- boot
- bush
- grommet
- insert
- bellows

The supply graph must therefore support:

```text
Ferrari assembly
    ↓
repairable by
    ↓
aftermarket subcomponent
```

This allows a complete Ferrari assembly to be repaired instead of replaced.

---

# 30. Service Templates

The same catalogue graph will eventually support service templates.

Examples:

```text
3-year cam belt service
full rubber replacement
cooling system refresh
annual service
zero-time rebuild
```

A service template expands into the correct model-specific BOM.

Example:

```text
vehicle
    ↓
3-year cam belt service
    ↓
complete required BOM
    ↓
correct Ferrari part numbers
    ↓
correct quantities
```

---

# 31. Sourcing Policy

A mechanic should eventually be able to choose a sourcing policy.

Examples:

```text
Recommended
OEM First
All OEM
Lowest Cost
```

`All OEM` requires an optional NLA override.

Example:

```text
All OEM

31 lines available from Ferrari
7 lines NLA

Allow validated NLA replacements
```

That override permits aftermarket substitution only where Ferrari cannot supply the required component.

---

# 32. Rubber Strategy

Rubber is a particularly attractive initial aftermarket category because ageing vehicles naturally generate demand for:

- hoses
- seals
- boots
- bushes
- grommets
- bellows
- isolators
- O-rings
- mounts
- weather seals

Existing aftermarket products should be used where suitable.

NLA Global does not need to manufacture every component.

The data identifies:

```text
complete job requirement
minus existing Ferrari supply
minus validated aftermarket supply
equals unresolved demand
```

Those unresolved components become candidates for additional manufacture.

---

# 33. NLA Global as Marketing Layer

NLA Global is principally the:

- demand layer
- catalogue intelligence layer
- application mapping layer
- quality and validation layer
- branding layer
- marketing layer
- workshop workflow layer
- customer transaction layer

Manufacturing may be outsourced.

The production partner knows how to manufacture the component.

NLA Global knows:

- what should be manufactured
- what Ferrari part it replaces
- which vehicles use it
- how many are required
- which service jobs consume it
- how often customers need it
- what existing alternatives exist
- where unresolved demand remains

---

# 34. Demand Intelligence

Use of the system creates real demand data.

For every Ferrari part number the system can eventually know:

```text
vehicles requiring it
jobs requesting it
units requested
Ferrari supply state
supplier availability
successful procurement
failed procurement
accepted pricing
unfulfilled demand
```

This identifies aftermarket manufacturing opportunities based on actual transaction intent rather than guesses.

---

# 35. Workshop Workflow

The intended mechanic experience becomes:

```text
select customer vehicle
    ↓
select service or parts
    ↓
complete BOM generated
    ↓
review
    ↓
quote
    ↓
client approval
    ↓
procure
    ↓
track parts in transit
```

For mature service templates the interaction may collapse to approximately:

```text
Car
→ Job
→ Quote
```

The complexity remains underneath.

---

# 36. Client Workflow

The client receives a clear workshop quote rather than an EPC research exercise.

The client may eventually:

```text
review
→ approve
```

Approval authorises procurement.

---

# 37. Procurement

After approval, the mechanic sees the authorised BOM.

Initially some OEM Ferrari orders may still need to be placed manually.

NLA Global can automate or directly fulfil the remainder.

Long term:

```text
approved BOM
    ↓
supplier resolution
    ↓
orders
    ↓
tracking
    ↓
all parts received
```

The mechanic should be able to see that all required components are either:

- ordered
- in transit
- delivered
- unresolved

---

# 38. Future Database Shape

Likely entities include:

```text
makers
models
submodels
diagrams
diagram-targets
parts
part-applications
supplier-products
supplier-product-parts
suppliers
supplier-offers
supersessions
replacement-parts
repair-components
vehicles
users
jobs
job-parts
service-templates
service-template-parts
orders
shipments
```

These names describe conceptual entities.

The eventual physical database naming convention may be chosen separately.

The canonical public path and filename convention remains hyphen based regardless of database implementation.

---

# 39. Core Data Relationship

The system revolves around:

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

The image provides spatial navigation.

The callout connects the image to the catalogue.

The Ferrari part number connects catalogue demand across models.

The supply graph resolves availability.

The job converts catalogue knowledge into a transaction.

---

# 40. Immediate Migration

Current image location:

```text
/wp-content/uploads/images/ferrari/360/360-modena/
```

Target image location:

```text
/wp-content/uploads/images/ferrari/ferrari-360/360-modena/
```

Existing files such as:

```text
360-modena-001.jpg
360-modena-002.jpg
```

must use the universal hyphen naming convention.

Prototype data moves to:

```text
/wp-content/uploads/data/ferrari/ferrari-360/360-modena/parts.json
```

All JSON image references must use the canonical new paths.

---

# 41. Derived File Naming

If intermediate or derived files are retained, they must follow the same grammar.

Examples:

```text
360-modena-001.jpg
360-modena-001-targets.json
360-modena-001-ocr.json
360-modena-001-overlay.png
360-modena-001-debug.png
```

No derived processing stage may introduce a second separator convention.

---

# 42. Immediate Implementation Sequence

1. Rename all diagram files to universal hyphen form.

2. Move them to:

```text
images/ferrari/ferrari-360/360-modena/
```

3. Move prototype data to:

```text
data/ferrari/ferrari-360/360-modena/parts.json
```

4. Update every image reference in `parts.json`.

5. Merge detected callout coordinates into the canonical `parts.json`.

6. Manually correct missing callouts including `38` and `49`.

7. Keep the detector as a separate offline enrichment process.

8. Modify viewer JavaScript to create positioned live nodes over callout numbers.

9. Add Ferrari centre status colours:

```text
green
orange
red
```

10. Add NLA Global border states:

```text
grey
green
blue
```

11. Move magnifier and fullscreen controls into the grey toolbar above the image.

12. Add the two-row Ferrari and NLA Global legend.

13. Preserve the current part modal.

14. Preserve selection functionality while the wishlist evolves into a proper job/BOM.

15. Ensure the viewer consumes only the canonical new path structure.

---

# 43. Acceptance Criteria

The prototype is successful when:

- canonical paths use lowercase hyphen-separated naming throughout
- no canonical path or filename uses an underscore
- the catalogue hierarchy can be inferred from the directory path
- all Ferrari 360 Modena diagrams use the new canonical directory
- all diagrams use the new canonical filename convention
- `parts.json` is the single temporary prototype data source
- displayed diagrams are the raw harvested Ferrparts images
- every known callout has a positional node
- missing detected callouts can be corrected in data without viewer changes
- nodes remain correctly aligned at any displayed image size
- hovering clearly identifies live nodes
- clicking a node opens the correct Ferrari part
- Ferrari status and NLA Global status are visually independent
- selected parts use a blue surrounding border
- no status information is permanently painted into the raw image
- the legend does not obscure diagram content
- magnifier and fullscreen controls do not obscure diagram content
- the eventual replacement of JSON by database/API data does not require redesigning the interaction model

---

# 44. Core Principles

## The image is the interface

The exploded diagram is not decoration.

It is the primary navigation surface.

## Ferrari part number is the catalogue anchor

It joins:

```text
diagrams
models
applications
suppliers
alternatives
jobs
```

## The filesystem describes the catalogue

```text
maker
→ maker-model
→ submodel
→ diagram
```

is visible directly in the path.

## JSON is temporary convenience

For the prototype:

```text
one submodel
→ one parts.json
```

Later the same interface is driven by the database.

## Status is live

The image remains unchanged.

The application dynamically paints meaning onto the numbered nodes.

## One naming grammar everywhere

Canonical catalogue paths and filenames are always:

```text
lowercase
hyphen separated
```

There is no second filename grammar to remember.

## The eventual product compresses complexity

The user experiences:

```text
see part
→ click
→ select
```

or:

```text
choose vehicle
→ choose service
→ quote
```

while the system handles the catalogue, quantities, availability, substitutions, suppliers and procurement underneath.

---

# 45. Product Direction

The long-term objective is:

> **Amazon 1-Click applied to old cars and NLA parts.**

For the mechanic:

```text
Car
→ Job
→ Quote
→ Approval
→ Procurement
→ Track
```

For the owner:

```text
Where unavailable doesn’t mean unobtainable.
```

For the catalogue architecture:

```text
IMAGE
→ CALLOUT
→ FERRARI PART NUMBER
→ SUPPLY
→ JOB
```

Everything in the current prototype should move us toward that model without creating naming conventions or data structures that have to be unwound later.
