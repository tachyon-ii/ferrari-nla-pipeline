# JSON → MySQL Mapping

## Purpose

The current Ferrari NLA prototype uses:

```text
data/{maker}/{maker-model}/{submodel}/parts.json
```

as a convenient single-file database.

Example:

```text
data/ferrari/ferrari-360/360-modena/parts.json
```

This is intentional.

The JSON file lets us develop and change the catalogue, diagram interaction and availability UI without first building the full relational backend.

The eventual production architecture will move the same logical information into MySQL.

This document defines the relationship between:

```text
prototype JSON
        ↓
relational MySQL model
```

The objective is not to make the JSON imitate SQL.

The objective is to ensure that the prototype data can be migrated cleanly without redesigning the application.

---

# 1. Core Principle

The logical chain is:

```text
MAKER
  ↓
MODEL
  ↓
SUBMODEL
  ↓
DIAGRAM
  ↓
CALLOUT
  ↓
FERRARI PART NUMBER
  ↓
SUPPLY GRAPH
  ↓
JOB / BOM
```

The JSON may flatten these relationships for convenience.

MySQL should model them properly.

---

# 2. Current JSON Role

During prototype development, `parts.json` may contain:

- maker
- model
- submodel
- diagrams
- diagram image paths
- diagram callout coordinates
- Ferrari part numbers
- descriptions
- Ferrari availability
- NLA Global availability
- supplier listings
- supersessions
- substitutions
- quantities
- prototype selection state

Example conceptual structure:

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
          "quantity": 1,
          "listings": []
        }
      ]
    }
  ]
}
```

This is convenient but deliberately denormalised.

---

# 3. MySQL Design Goals

The MySQL schema should:

1. avoid duplicate canonical data;
2. use Ferrari part number as the canonical Ferrari part identity;
3. allow one Ferrari part to appear on many diagrams and models;
4. allow one diagram callout to map to more than one Ferrari part;
5. preserve source-image coordinates exactly;
6. separate Ferrari status from NLA Global status;
7. support multiple suppliers for one part;
8. support kits and products covering multiple Ferrari part numbers;
9. support repair components below Ferrari catalogue granularity;
10. support quantity rules by application;
11. support supersessions and substitutions;
12. support service templates;
13. support vehicle-specific jobs and BOMs;
14. support future procurement and order tracking;
15. retain provenance for imported and enriched data.

---

# 4. Identity Rules

## Maker

Example:

```text
ferrari
```

## Model

Example:

```text
ferrari-360
```

## Submodel

Example:

```text
360-modena
```

## Diagram

Example:

```text
360-modena-001
```

## Ferrari Part

Canonical identity:

```text
Ferrari part number
```

Example:

```text
179280
```

The Ferrari part number must not be recreated separately for every diagram occurrence.

---

# 5. Proposed Core Tables

Initial core tables:

```text
makers
models
submodels
diagrams
diagram-targets
parts
part-applications
```

Supply tables:

```text
suppliers
supplier-products
supplier-product-parts
supplier-offers
```

Relationship tables:

```text
supersessions
replacement-parts
repair-components
quantity-rules
```

Workflow tables:

```text
vehicles
jobs
job-parts
service-templates
service-template-parts
orders
order-items
shipments
```

Provenance/enrichment tables may be added later.

---

# 6. `makers`

Represents marques.

Example row:

```text
id      1
slug    ferrari
name    Ferrari
```

Possible fields:

```sql
id
slug
name
created-at
updated-at
```

`slug` should be unique.

---

# 7. `models`

Represents model families.

Example:

```text
Ferrari 360
```

Possible fields:

```sql
id
maker-id
slug
name
created-at
updated-at
```

Example:

```text
maker-id = 1
slug     = ferrari-360
name     = Ferrari 360
```

Constraint:

```text
maker + slug
```

must be unique.

---

# 8. `submodels`

Represents individual catalogue variants.

Example:

```text
360 Modena
360 Spider
360 Challenge Stradale
```

Possible fields:

```sql
id
model-id
slug
name
production-start
production-end
notes
created-at
updated-at
```

Example:

```text
slug = 360-modena
```

---

# 9. `diagrams`

Represents a single exploded diagram.

Possible fields:

```sql
id
submodel-id
diagram-number
slug
title
image-path
image-width
image-height
sort-order
created-at
updated-at
```

Example:

```text
diagram-number = 001
slug           = 360-modena-001
title          = Crankcase
image-path     = ferrari/ferrari-360/360-modena/360-modena-001.jpg
```

The image path may be derived from taxonomy, but storing the resolved canonical path is still useful.

---

# 10. `diagram-targets`

Represents a clickable numbered callout on a diagram.

This is spatial data.

Possible fields:

```sql
id
diagram-id
callout
x
y
w
h
created-at
updated-at
```

Example:

```text
diagram-id = 17
callout    = 38
x          = 412
y          = 237
w          = 20
h          = 15
```

Coordinates are stored in source-image pixels.

Do not store normalised coordinates.

A uniqueness constraint should normally exist on:

```text
diagram-id + callout
```

unless a future source requires the same callout number to appear in multiple independent regions.

---

# 11. `parts`

Represents canonical Ferrari parts.

Possible fields:

```sql
id
maker-id
part-number
description
ferrari-status
notes
created-at
updated-at
```

Example:

```text
part-number    = 179280
description    = Water hose
ferrari-status = available
```

Ferrari part number should be unique within maker.

Constraint:

```text
maker-id + part-number
```

must be unique.

This allows the same schema to support other marques later.

---

# 12. `part-applications`

Maps Ferrari parts to diagram callouts and vehicle applications.

Possible fields:

```sql
id
part-id
diagram-target-id
submodel-id
variant-note
quantity
from-chassis
to-chassis
created-at
updated-at
```

Core relationship:

```text
diagram target
    ↓
part application
    ↓
canonical part
```

This is important because:

- the same part can occur on many diagrams;
- the same callout can resolve differently depending on vehicle variant;
- one callout may represent several possible Ferrari part numbers.

---

# 13. Why `diagram-targets` and `part-applications` Are Separate

A callout is spatial.

A part application is semantic.

Example:

```text
callout 38
x=412
y=237
```

is a property of the diagram.

The fact that callout 38 means Ferrari PN `179280` is a catalogue relationship.

Keeping these separate avoids contaminating spatial data with vehicle-specific part logic.

---

# 14. Ferrari Availability

Ferrari availability belongs to the canonical Ferrari part or to a time-based Ferrari supply record.

Prototype:

```text
ferrari-status
```

Initial values:

```text
available
special-order
nla
unknown
```

The UI maps:

```text
available       → green
special-order   → orange
nla             → red
```

Long term, Ferrari status may deserve its own history table because availability can change over time.

Possible future table:

```text
part-status-history
```

with:

```sql
part-id
status
observed-at
source
```

---

# 15. NLA Global Availability

NLA Global status is not the same thing as Ferrari status.

Prototype values:

```text
unknown
available
selected
```

`selected` should not become a permanent part status in MySQL.

Selection belongs to a job.

Therefore the eventual relational model should distinguish:

```text
NLA Global supply capability
```

from:

```text
current user/job selection
```

NLA Global supply capability can be derived from supplier offers and validated alternatives.

---

# 16. Suppliers

## `suppliers`

Possible fields:

```sql
id
slug
name
website
country
active
created-at
updated-at
```

Examples may include:

```text
Ferrari
AW Italian
Ferrari Parts Exchange
NLA Global
```

---

# 17. `supplier-products`

Represents something a supplier actually sells.

This is deliberately separate from Ferrari part number.

Possible fields:

```sql
id
supplier-id
supplier-sku
name
url
product-type
active
created-at
updated-at
```

Example:

```text
AW5360000
```

A supplier product may be:

- direct replacement
- kit
- aftermarket component
- repair component
- NOS item
- used item
- remanufactured item

---

# 18. `supplier-product-parts`

Many-to-many mapping between supplier products and Ferrari part numbers.

Possible fields:

```sql
supplier-product-id
part-id
quantity
relationship
```

Example:

```text
supplier product AW5360000
    ↓
covers Ferrari PN 176161
covers Ferrari PN 177513
covers Ferrari PN 177514
...
```

This is necessary because one supplier kit may cover many Ferrari part numbers.

Likewise one Ferrari part number may have many supplier products.

---

# 19. `supplier-offers`

Represents current commercial availability.

Possible fields:

```sql
id
supplier-product-id
price
currency
stock-status
lead-time
observed-at
source
created-at
updated-at
```

Examples:

```text
in-stock
special-order
out-of-stock
unknown
```

Price and availability are observations, not immutable product attributes.

---

# 20. Supersessions

Ferrari may supersede one OEM part number with another.

Table:

```text
supersessions
```

Possible fields:

```sql
id
old-part-id
new-part-id
source
effective-date
notes
```

Relationship:

```text
Ferrari PN A
    ↓ superseded by
Ferrari PN B
```

---

# 21. Replacement Parts

Not every alternative is an official supersession.

Table:

```text
replacement-parts
```

Possible fields:

```sql
id
original-part-id
replacement-part-id
relationship
confidence
validated
notes
```

Possible relationships:

```text
direct-replacement
compatible
aftermarket-equivalent
upgrade
```

---

# 22. Repair Components

Some Ferrari catalogue items can be repaired using subcomponents Ferrari does not catalogue separately.

Example:

```text
Ferrari assembly
    ↓
repairable using
aftermarket seal
```

Table:

```text
repair-components
```

Possible fields:

```sql
id
parent-part-id
supplier-product-id
description
validated
notes
```

This lets the supply graph go below Ferrari catalogue granularity.

---

# 23. Quantity Rules

Quantity is often application-specific.

Do not assume:

```text
part number → one universal quantity
```

Examples:

```text
spark plug      8 per V8 engine
hose            2 per vehicle
sensor          4 per engine
bush            2 per axle
```

Table:

```text
quantity-rules
```

Possible fields:

```sql
id
part-id
submodel-id
service-template-id
quantity
basis
confidence
source
notes
```

Possible `basis` values:

```text
per-vehicle
per-engine
per-cylinder
per-bank
per-axle
per-side
per-job
```

---

# 24. Service Templates

Table:

```text
service-templates
```

Possible fields:

```sql
id
model-id
submodel-id
slug
name
description
active
```

Examples:

```text
3-year-cam-belt-service
full-rubber-replacement
annual-service
cooling-system-refresh
```

---

# 25. `service-template-parts`

Maps a service template to its required parts.

Possible fields:

```sql
id
service-template-id
part-id
default-quantity
required
notes
```

The service template creates a model-specific BOM.

---

# 26. Vehicles

Table:

```text
vehicles
```

Possible fields:

```sql
id
user-id
maker-id
model-id
submodel-id
vin
chassis-number
registration
build-date
notes
```

The vehicle allows later filtering by:

- exact submodel
- build date
- chassis range
- transmission
- market variant

---

# 27. Jobs

Table:

```text
jobs
```

Possible fields:

```sql
id
vehicle-id
workshop-id
service-template-id
status
created-at
updated-at
```

Example statuses:

```text
draft
quoted
approved
ordering
in-progress
complete
```

---

# 28. `job-parts`

This is where `Selected` ultimately belongs.

Possible fields:

```sql
id
job-id
part-id
quantity
source-preference
approved
status
notes
```

Diagram node:

```text
blue border
```

means that the associated part is present in the current job/BOM.

It is not a permanent property of the part.

---

# 29. Procurement

Future tables:

```text
orders
order-items
shipments
```

These support:

```text
approved BOM
    ↓
supplier resolution
    ↓
orders
    ↓
tracking
    ↓
delivered
```

---

# 30. JSON → MySQL Mapping

Approximate mapping:

| JSON | MySQL |
|---|---|
| `maker` | `makers` |
| `model` | `models` |
| `submodel` | `submodels` |
| diagram object | `diagrams` |
| `callout`, `x`, `y`, `w`, `h` | `diagram-targets` |
| `part-number` | `parts` |
| diagram → part relation | `part-applications` |
| `ferrari-status` | `parts` or status history |
| `nla-status` | derived supply state |
| `quantity` | `quantity-rules` or application |
| `listings` | `supplier-products` + `supplier-offers` |
| `selected` | `job-parts` |

---

# 31. Example Relational Expansion

Prototype JSON:

```json
{
  "diagram-number": "001",
  "parts": [
    {
      "callout": "38",
      "x": 412,
      "y": 237,
      "w": 20,
      "h": 15,
      "part-number": "179280",
      "description": "Water hose",
      "ferrari-status": "nla",
      "nla-status": "available"
    }
  ]
}
```

becomes conceptually:

```text
diagrams
--------
id = 17
submodel-id = 3
diagram-number = 001

diagram-targets
---------------
id = 845
diagram-id = 17
callout = 38
x = 412
y = 237
w = 20
h = 15

parts
-----
id = 922
maker-id = Ferrari
part-number = 179280
description = Water hose
ferrari-status = nla

part-applications
-----------------
diagram-target-id = 845
part-id = 922

supplier-products
-----------------
...

supplier-product-parts
----------------------
supplier-product-id = ...
part-id = 922

supplier-offers
---------------
...
```

The viewer can reconstruct exactly the same runtime object.

---

# 32. API Shape

The eventual API does not need to expose the normalised SQL structure directly.

It can return a convenient viewer object similar to the current JSON.

For example:

```json
{
  "diagram-number": "001",
  "image": "/wp-content/uploads/images/ferrari/ferrari-360/360-modena/360-modena-001.jpg",
  "parts": [
    {
      "callout": "38",
      "x": 412,
      "y": 237,
      "w": 20,
      "h": 15,
      "part-number": "179280",
      "description": "Water hose",
      "ferrari-status": "nla",
      "nla-status": "available",
      "selected": false
    }
  ]
}
```

This means:

```text
JSON prototype shape
```

can evolve naturally into:

```text
API response shape
```

even though the database underneath is normalised.

That is the migration bridge.

---

# 33. Migration Strategy

The migration should happen incrementally.

## Phase 1

Current:

```text
parts.json
```

is authoritative.

## Phase 2

Create MySQL tables and import JSON.

JSON remains available for comparison.

## Phase 3

Database becomes authoritative.

Generate the same viewer payload from MySQL.

## Phase 4

Viewer switches from:

```text
static parts.json
```

to:

```text
API/database-backed JSON response
```

The frontend interaction model should not materially change.

---

# 34. Import Requirements

The JSON importer should be idempotent where practical.

Repeated import should update existing canonical entities rather than create duplicates.

Natural identifiers include:

```text
maker slug
model slug
submodel slug
diagram number
Ferrari part number
diagram + callout
supplier + supplier SKU
```

Surrogate numeric IDs may still be used internally.

---

# 35. Provenance

Catalogue data comes from multiple sources.

Long term we should retain provenance for fields such as:

```text
Ferrari part mapping
availability
price
quantity
supersession
replacement
supplier coverage
```

Possible generic provenance fields:

```sql
source
source-url
observed-at
confidence
method
```

Possible methods:

```text
scraped
manual
OCR
LLM-enriched
supplier-confirmed
purchase-confirmed
```

A successful purchase is stronger evidence of supply than a catalogue listing.

---

# 36. Confidence

Not all enriched information has equal certainty.

For derived fields such as quantity or compatibility, useful confidence states may include:

```text
confirmed
high
medium
low
unknown
```

Unknown should remain unknown.

The system must not invent values merely to fill the schema.

---

# 37. Status Is Time-Dependent

Supplier price and stock are inherently time-dependent.

Ferrari availability may also change.

Therefore:

```text
current status
```

should ultimately be understood as:

```text
most recent trusted observation
```

rather than an eternal property.

This becomes important when we begin periodic supplier refresh.

---

# 38. Demand Data

Once jobs exist, the database can measure:

```text
part requested
quantity requested
vehicle/application
Ferrari status
available alternatives
successful procurement
failed procurement
accepted price
unfulfilled demand
```

This creates the aftermarket opportunity queue.

Conceptually:

```text
Ferrari PN
→ annual demand
→ unresolved demand
→ affected installed base
→ manufacturing opportunity
```

---

# 39. Database Naming

The canonical public filesystem uses hyphens.

MySQL physical identifiers may use standard SQL naming conventions.

For example:

```text
diagram_targets
supplier_products
part_applications
```

is preferable in SQL to requiring quoted identifiers such as:

```text
diagram-targets
```

The **no underscore rule applies to canonical project paths, slugs and filenames**, not necessarily to SQL identifiers.

This distinction is deliberate.

Public/catalogue identity:

```text
360-modena-001
```

SQL implementation:

```text
diagram_targets
```

Do not sacrifice normal SQL ergonomics merely to imitate filesystem naming.

---

# 40. Foreign Keys

Foreign keys should be used for stable structural relationships.

Examples:

```text
models.maker_id
submodels.model_id
diagrams.submodel_id
diagram_targets.diagram_id
part_applications.part_id
part_applications.diagram_target_id
supplier_products.supplier_id
job_parts.job_id
job_parts.part_id
```

Deletion policy should be conservative.

Catalogue records should usually be retired or marked inactive rather than cascaded away.

---

# 41. Soft State

Some records should have states such as:

```text
active
inactive
deprecated
superseded
```

rather than being deleted.

This is especially important for:

- parts
- supplier products
- supersessions
- vehicle applications
- service templates

Historical catalogue identity has value.

---

# 42. Indexing

Likely important indexes include:

```text
parts(part_number)
diagram_targets(diagram_id, callout)
part_applications(part_id)
part_applications(diagram_target_id)
supplier_product_parts(part_id)
supplier_offers(supplier_product_id, observed_at)
job_parts(job_id)
```

Search requirements will evolve as the catalogue grows.

---

# 43. Initial Minimum MySQL Schema

The first database version does not need the entire future system.

Minimum useful migration:

```text
makers
models
submodels
diagrams
diagram_targets
parts
part_applications
suppliers
supplier_products
supplier_product_parts
supplier_offers
```

This is enough to move the core illustrated catalogue and sourcing graph out of static JSON.

Jobs and service templates can follow.

---

# 44. What Must Not Be Lost During Migration

The database migration must preserve:

- canonical maker/model/submodel identity
- diagram numbering
- canonical image paths
- original image width and height
- exact callout pixel coordinates
- Ferrari part numbers
- descriptions
- diagram-to-part relationships
- application-specific differences
- Ferrari availability
- supplier relationships
- provenance
- unknown values

Do not convert `unknown` into guessed data.

---

# 45. Prototype Contract

The current JSON is not disposable in the sense of being meaningless.

It defines the first version of the runtime contract.

The viewer expects to obtain:

```text
diagram
image
callout
coordinates
part number
description
Ferrari status
NLA Global status
selection state
```

Today:

```text
parts.json
```

provides that contract.

Later:

```text
MySQL
    ↓
API
    ↓
same logical viewer object
```

provides it.

---

# 46. Architectural Principle

The relational database should model reality correctly.

The API should present data conveniently.

The frontend should remain simple.

Therefore:

```text
NORMALISED MYSQL
       ↓
APPLICATION QUERY
       ↓
CONVENIENT JSON
       ↓
DIAGRAM VIEWER
```

The prototype begins at the third layer.

The production system eventually supplies that same layer from the first two.

---

# 47. Core Relationship

The essential data graph remains:

```text
IMAGE
  ↓
DIAGRAM TARGET
  ↓
CALLOUT
  ↓
PART APPLICATION
  ↓
FERRARI PART NUMBER
  ↓
SUPPLIER / REPLACEMENT GRAPH
  ↓
JOB / BOM
```

That relationship should survive every implementation change.

The JSON is temporary.

The graph is not.
