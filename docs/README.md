# docs/

Project documentation, engineering decision records, and technical specifications:

- [`system_overview.md`](system_overview.md) — **System documentation:** full architecture, AI model summary, dashboard API, serial protocol, configuration reference, and deployment gotchas. Start here.
- [`scope_delimitation.md`](scope_delimitation.md) — System boundaries, capabilities, academic delimitations (PCU-D), and operational constraints.
- [`bom.md`](bom.md) — Itemized Bill of Materials with hardware specifications, estimated component costs (PHP/USD), and procurement status.
- [`design_rationale.md`](design_rationale.md) — Architectural Decision Records (ADRs) covering OS choice, heterogeneous compute, model pivot, and compute-aware triggering.
- [`calibration_procedure.md`](calibration_procedure.md) — Post-mounting calibration procedure for quadrant pan/tilt angles, LDR thresholds, camera exposure/gain, and motion sensitivity.
- [`dataset_and_training.md`](dataset_and_training.md) — Dataset specifications (SCUT-HEAD Part A + Local Classroom), head annotation conventions, and TFLite quantization.
- [`benchmark_results.md`](benchmark_results.md) — Baseline model validation records, Pi 3B latency benchmarks, power/thermal profiling, and field testing protocol.
- [`direct_connection.md`](direct_connection.md) — Headless connectivity options: direct ethernet (Option A), USB gadget/RNDIS (Option B), and Wi-Fi hotspot/`hotspot.sh` (Option C — no cables, Pi broadcasts its own `CLASSCAN` AP).
- [`novelty_and_competitive_analysis.md`](novelty_and_competitive_analysis.md) — Novelty statement and competitive landscape: how CLASSCAN differs from commercial people-counters, cloud SaaS, generic open-source pipelines, RFID attendance systems, and facial recognition approaches.

