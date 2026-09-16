# AI Vision — Future Step (Intentionally Postponed)

**Step 7 — AI Vision: intentionally postponed.**

## Current state

AI Vision is the next planned stage of Midori. It is **intentionally not implemented
in this development cycle**. The pipeline currently ends at the image-quality gate:

```text
Image Intake → Image Quality → READY_FOR_AI → [AI VISION — NOT IMPLEMENTED YET]
```

## What the current system does and does not do

- Image Intake and Image Quality **prepare** images for future AI processing.
- `READY_FOR_AI` means the image passed intake validation and quality checks.
- `READY_FOR_AI` does **NOT** mean the image has been analyzed by any AI.
- **No disease or pest diagnosis** can currently be claimed from any image.
- **No AI confidence** value is currently generated anywhere in the system.
- **No severity** may be derived from AI output yet — the Severity Engine is also future work.

## Downstream modules (also future steps)

Because AI Vision is postponed, everything that depends on its output is deferred too:

- Expert Validation workflow (human-in-the-loop review of AI predictions)
- Final Assessment record (risk + AI observation + expert review)
- Severity Engine
- Advisory backend
- Alerts / Follow-up

These will be built in order once AI Vision lands.

## Why postpone?

A correct, fully verified Steps 1–6 system is worth more than a half-working AI
module. The image-intake contract (`READY_FOR_AI` + metadata + safe storage) is
stable and documented, so AI Vision can be plugged in later without touching any
existing module.

## Design commitments for when AI Vision is built

1. **Verified agricultural models only** — candidates such as PlantDoc (crop
   disease) and IP102 (pests) must have their checkpoint, license, classes and
   preprocessing verified and documented **before** any download. No random
   checkpoints, no fabricated URLs, no fake diagnoses hard-coded.
2. **Inference abstraction** — AI Vision sits behind a service interface with a
   model adapter layer, so the runtime (PyTorch CPU / ONNX Runtime) and the model
   itself are replaceable without touching the API.
3. **Model registry** — name, version, source, dataset, license, checkpoint path,
   class list, preprocessing, recorded per model, for reproducibility.
4. **No inference at request time downloads models** — model setup is an explicit
   development operation; missing checkpoints produce controlled errors.
5. **Confidence is exposed, never embellished** — model confidence is not a
   validated disease probability; low-confidence results route to expert review,
   never to automatic confirmation.
6. **Deterministic tests** — the test suite will use tiny deterministic fixture
   models, never real 200 MB checkpoints or network downloads.

## Note on local work-in-progress

A local, unverified work-in-progress `app/ai/` prototype exists on the development
machine but is **excluded from the committed repository**. It is not documented as
a completed feature and will be rebuilt/reviewed properly when Step 7 starts.
