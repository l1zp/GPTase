# Web UI Design: Scientific Laboratory Theme

## Overview

The GPTase Agent Sessions page features a **Scientific Laboratory** aesthetic with animated workflow visualization.

## Design Theme

**Aesthetic**: Scientific Laboratory + Animated Workflow Visualization
- **Tone**: Technical precision meets bio-luminescent beauty
- **Inspiration**: Lab terminal interfaces, fluorescence microscopy displays
- **Key Differentiator**: Pulsing neon workflow nodes

## Color Palette

| Variable | Value | Purpose |
|----------|-------|---------|
| `--lab-bg-dark` | #0a0e0f | Deep background |
| `--lab-bg-panel` | #0d1419 | Panel background |
| `--lab-neon-green` | #00ff9d | Bio-luminescent green |
| `--lab-neon-blue` | #00d4ff | Cyan fluorescence |
| `--lab-neon-purple` | #a855f7 | Accent purple |
| `--lab-text-primary` | #e0f2fe | Light text |
| `--lab-text-secondary` | #94a3b8 | Muted text |

## Typography

- **Display Font**: System UI fonts for headers
- **Mono Font**: SF Mono, Fira Code, Consolas for technical content

## Key Visual Effects

### Animated Header Glow
- 2px animated gradient bar
- 3s glow-pulse cycle

### Pulsing Workflow Nodes
- Pulsing circular indicator
- 2s cycle for completed, 1.5s for in-progress

### Status Badges
- Glowing border animation
- Status-based colors (green/blue/red)

## Usage

```bash
streamlit run src/webui/app.py
```

Navigate to **"Agent Sessions"** to see:
- Dark lab-themed interface
- Neon green/blue accents
- Animated workflow steps
- Glowing status indicators
- Monospace technical fonts

## File Locations

- CSS: [src/webui/app.py](../src/webui/app.py) (lines 23-326)
- Alternative theme: [src/webui/lab_theme.css](../src/webui/lab_theme.css)
- View implementation: [src/webui/extraction_sessions_lab.py](../src/webui/extraction_sessions_lab.py)

---

**Generated**: 2026-01-23
