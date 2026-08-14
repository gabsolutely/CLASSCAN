# CLASSCAN

**Development of an Intelligent Classroom Headcount Monitoring System using Computer Vision and LED Display Technology**

A ceiling-mounted smart camera turret that automatically detects and counts people in a classroom in real time, displaying the live headcount on an LED display — no manual attendance checking, no face recognition, just occupancy.

> Status: Design & documentation phase — hardware/software implementation in progress.

---

## The Problem

Most schools still rely on manual headcount and attendance checking — slow, error-prone, and unhelpful in situations like emergencies or class transitions where a fast, accurate room count actually matters. CLASSCAN automates this using computer vision and a real-time display, without collecting any identifying information about students.

## What It Does

- Detects and counts people in a classroom using a live camera feed
- Displays the current headcount on an LED display in real time
- Automatically switches to IR illumination in low-light conditions (no visible light shone on students)
- Uses pan/tilt servos to sweep the room for wider coverage from a single ceiling-mounted unit
- Runs on swappable battery power for flexible testing across rooms

## What It Does NOT Do

- No facial recognition
- No individual student identification
- No attendance logging by name
- Not a security/surveillance system — occupancy count only

## How It Works

```
loop every N seconds:
    check light sensor
    if dim: turn on IR illuminator (invisible to people)
    else: IR illuminator off

    capture camera frame(s) across pan/tilt sweep positions
    run person-detection model on each frame
    merge/deduplicate counts across sweep positions
    display total headcount on LED display
```

## Hardware

| Component | Purpose |
|---|---|
| Orange Pi 3B | Main compute — runs the person-detection model |
| Pi NoIR Camera Module | Video feed, functions in low light with IR |
| IR Illuminator Module | Invisible-to-humans illumination for dim rooms |
| Light Sensor (LDR) | Detects ambient brightness, triggers IR illuminator |
| Pan/Tilt Servos (MG90S) | Rotates the turret to sweep the room |
| LED Matrix Display | Shows live headcount |
| 18650 Battery + Charging Module | Swappable, untethered power |
| 3D-Printed Dome Enclosure | Houses all components, ceiling-mounted |

Full itemized BOM and cost breakdown: see `/docs` *(update path once added)*.

## Repository Structure

```
/docs         → Scope & Delimitation, Significance, BOM, design docs
/cad          → Enclosure design files/renders
/src          → (planned) CV model, detection logic, display driver
/hardware     → (planned) wiring diagrams, GPIO pinout
```

*(Adjust structure above to match actual repo layout once code is added.)*

## Team

*(Add contributors here — e.g. names + roles: Hardware/Enclosure, CV/AI Model, Embedded/Firmware, Documentation)*

## Academic Context

This is a Senior High School STEM capstone project developed at Philippine Christian University, Dasmariñas (PCU-D).

---

*This README will be updated as the CV model, firmware, and hardware assembly progress from design to implementation.*
