# Web UI Theme Guide

Detailed documentation for the Scientific Laboratory theme used in the GPTase Streamlit web interface.

## Overview

The Web UI features a custom Scientific Laboratory theme with dark background, neon green/blue bio-luminescent accents, and monospace fonts for technical precision.

## Color Palette

### Background Colors

```css
/* Primary background gradient */
background: linear-gradient(135deg, #1a1f2e 0%, #0f1a1f 100%);

/* Secondary background */
background-color: #0d1117;

/* Card/panel background */
background-color: rgba(26, 31, 46, 0.8);
```

### Accent Colors

```css
/* Neon green - primary accent */
--neon-green: #00ff9d;

/* Neon blue - secondary accent */
--neon-blue: #00d4ff;

/* Status colors */
--success-color: #00ff9d;
--warning-color: #ffaa00;
--error-color: #ff4444;
--info-color: #00d4ff;
```

### Text Colors

```css
/* Primary text */
text-color: #e6edf3;

/* Secondary text */
text-color: #8b949e;

/* Muted text */
text-color: #6e7681;
```

## Typography

### Font Families

```css
/* Monospace for technical content */
font-family: 'SF Mono', 'Fira Code', 'Monaco', 'Consolas', monospace;

/* Sans-serif for headers */
font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
```

### Font Sizes

```css
/* Headers */
h1: 28px / 1.2
h2: 24px / 1.3
h3: 20px / 1.4

/* Body text */
p: 14px / 1.6

/* Small text */
small, .caption: 12px / 1.5

/* Code blocks */
code, pre: 13px / 1.5
```

## UI Components

### Buttons

```css
/* Primary button - neon green */
.primary-button {
    background: linear-gradient(135deg, #00ff9d 0%, #00cc7d 100%);
    color: #0d1117;
    border: none;
    box-shadow: 0 0 20px rgba(0, 255, 157, 0.3);
}

.primary-button:hover {
    box-shadow: 0 0 30px rgba(0, 255, 157, 0.5);
    transform: translateY(-2px);
}

/* Secondary button - neon blue */
.secondary-button {
    background: linear-gradient(135deg, #00d4ff 0%, #00a8cc 100%);
    color: #0d1117;
    border: none;
}
```

### Status Badges

```css
/* Completed status */
.badge-completed {
    background: rgba(0, 255, 157, 0.2);
    color: #00ff9d;
    border: 1px solid #00ff9d;
    box-shadow: 0 0 10px rgba(0, 255, 157, 0.3);
}

/* In-progress status */
.badge-in-progress {
    background: rgba(0, 212, 255, 0.2);
    color: #00d4ff;
    border: 1px solid #00d4ff;
    box-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
    animation: pulse 2s infinite;
}

/* Failed status */
.badge-failed {
    background: rgba(255, 68, 68, 0.2);
    color: #ff4444;
    border: 1px solid #ff4444;
}
```

### Workflow Nodes

```css
/* Animated pulsing nodes */
.workflow-node {
    background: rgba(26, 31, 46, 0.9);
    border: 2px solid #00ff9d;
    border-radius: 8px;
    box-shadow: 0 0 15px rgba(0, 255, 157, 0.4);
    animation: node-pulse 3s infinite;
}

@keyframes node-pulse {
    0%, 100% {
        box-shadow: 0 0 15px rgba(0, 255, 157, 0.4);
    }
    50% {
        box-shadow: 0 0 25px rgba(0, 255, 157, 0.7);
    }
}

/* Status-based colors */
.node-completed {
    border-color: #00ff9d;
    box-shadow: 0 0 15px rgba(0, 255, 157, 0.4);
}

.node-in-progress {
    border-color: #00d4ff;
    box-shadow: 0 0 15px rgba(0, 212, 255, 0.4);
    animation: node-pulse 2s infinite;
}

.node-failed {
    border-color: #ff4444;
    box-shadow: 0 0 15px rgba(255, 68, 68, 0.4);
}
```

### Expandable Sections

```css
/* Collapsible details panels */
.details-panel {
    background: rgba(13, 17, 23, 0.95);
    border: 1px solid #30363d;
    border-radius: 6px;
    margin: 10px 0;
}

.details-header {
    background: rgba(48, 54, 61, 0.5);
    padding: 12px 16px;
    cursor: pointer;
    transition: background 0.2s;
}

.details-header:hover {
    background: rgba(48, 54, 61, 0.8);
}

.details-content {
    padding: 16px;
    border-top: 1px solid #30363d;
}
```

### Scrollbar Styling

```css
/* Custom scrollbar */
::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: #0d1117;
}

::-webkit-scrollbar-thumb {
    background: linear-gradient(135deg, #00ff9d 0%, #00d4ff 100%);
    border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(135deg, #00cc7d 0%, #00a8cc 100%);
}
```

## Animations

### Pulse Animation

```css
@keyframes pulse {
    0%, 100% {
        opacity: 1;
        transform: scale(1);
    }
    50% {
        opacity: 0.8;
        transform: scale(1.05);
    }
}

/* Apply to status indicators */
.pulse-indicator {
    animation: pulse 2s infinite;
}
```

### Glow Effect

```css
@keyframes glow {
    0%, 100% {
        box-shadow: 0 0 5px rgba(0, 255, 157, 0.5);
    }
    50% {
        box-shadow: 0 0 20px rgba(0, 255, 157, 0.8);
    }
}

/* Apply to important elements */
.glow-element {
    animation: glow 3s infinite;
}
```

### Fade In

```css
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Apply to new content */
.fade-in {
    animation: fadeIn 0.3s ease-out;
}
```

## Layout Structure

### Main Container

```css
.main-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

/* Header */
.header {
    background: rgba(26, 31, 46, 0.95);
    border-bottom: 2px solid #00ff9d;
    padding: 20px;
    margin-bottom: 30px;
}

/* Content area */
.content {
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 20px;
}
```

### Sidebar

```css
.sidebar {
    background: rgba(13, 17, 23, 0.9);
    border-right: 1px solid #30363d;
    padding: 20px;
}

.sidebar-item {
    padding: 12px;
    margin: 8px 0;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.sidebar-item:hover {
    background: rgba(0, 255, 157, 0.1);
    border-left: 3px solid #00ff9d;
}

.sidebar-item.active {
    background: rgba(0, 255, 157, 0.2);
    border-left: 3px solid #00ff9d;
}
```

### Agent Sessions Hierarchy

```css
/* 4-level hierarchy display */
.hierarchy-container {
    margin-left: 20px;
}

/* Level 1: Agent */
.agent-level {
    font-size: 18px;
    font-weight: bold;
    color: #00ff9d;
    margin: 15px 0;
}

/* Level 2: Task */
.task-level {
    margin-left: 20px;
    padding: 10px;
    border-left: 2px solid #00d4ff;
}

/* Level 3: Job */
.job-level {
    margin-left: 40px;
    padding: 8px;
    border-left: 2px solid #8b949e;
}

/* Level 4: Details */
.details-level {
    margin-left: 60px;
    padding: 10px;
    background: rgba(26, 31, 46, 0.5);
    border-radius: 4px;
}
```

## Responsive Design

### Breakpoints

```css
/* Mobile */
@media (max-width: 768px) {
    .content {
        grid-template-columns: 1fr;
    }

    .sidebar {
        display: none;
    }
}

/* Tablet */
@media (min-width: 769px) and (max-width: 1024px) {
    .content {
        grid-template-columns: 250px 1fr;
    }
}

/* Desktop */
@media (min-width: 1025px) {
    .content {
        grid-template-columns: 300px 1fr;
    }
}
```

## Usage in Streamlit

### Applying Custom CSS

```python
import streamlit as st

# Define custom CSS
custom_css = """
<style>
    /* Your custom CSS here */
    .main-container {
        background: linear-gradient(135deg, #1a1f2e 0%, #0f1a1f 100%);
    }
</style>
"""

# Inject CSS
st.markdown(custom_css, unsafe_allow_html=True)
```

### Creating Animated Components

```python
import streamlit as st

# Animated status badge
st.markdown(
    f"""
    <div class="badge-in-progress pulse-indicator">
        IN_PROGRESS
    </div>
    """,
    unsafe_allow_html=True
)
```

### Workflow Visualization

```python
# Display hierarchy with styled nodes
st.markdown("""
<div class="hierarchy-container">
    <div class="agent-level">Agent (reaction_extractor)</div>
    <div class="task-level">
        Task 1: listov2025.md (COMPLETED, 2 jobs, 45.2s)
        <div class="job-level">
            Job 01: structure_analysis (COMPLETED)
        </div>
        <div class="job-level">
            Job 02: main_extraction (COMPLETED)
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
```

## Customization

### Changing Accent Colors

To customize the accent colors, modify the CSS variables:

```css
:root {
    --primary-accent: #00ff9d;  /* Change to your color */
    --secondary-accent: #00d4ff; /* Change to your color */
}
```

### Adjusting Animation Speed

Modify animation durations:

```css
.fast-pulse {
    animation: pulse 1s infinite;  /* Faster */
}

.slow-pulse {
    animation: pulse 5s infinite;  /* Slower */
}
```

### Darkening/Lightening Theme

Adjust background opacity:

```css
/* Darker theme */
.darker-theme {
    background: rgba(10, 15, 20, 0.98);
}

/* Lighter theme */
.lighter-theme {
    background: rgba(26, 31, 46, 0.6);
}
```

## Browser Compatibility

### Tested Browsers

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Opera 76+

### Known Issues

- **Safari < 14**: Custom scrollbar styling not supported
- **Firefox**: Gradient text may need vendor prefix
- **Mobile**: Reduced animation support for performance

## Performance Optimization

### CSS Optimization

```css
/* Use hardware acceleration for animations */
.animated-element {
    will-change: transform, opacity;
    transform: translateZ(0);
}

/* Reduce repaints with transforms instead of position changes */
.moving-element {
    transform: translateX(100px);  /* Good */
    /* left: 100px;  Bad - causes reflow */
}
```

### Animation Performance

- Limit concurrent animations (< 10 simultaneously)
- Use `transform` and `opacity` for smooth animations
- Avoid animating `width`, `height`, or `top/left`
- Test on lower-end devices

## Accessibility

### Color Contrast

All text meets WCAG AA standards:
- Normal text: 4.5:1 contrast ratio
- Large text: 3:1 contrast ratio
- UI components: 3:1 contrast ratio

### Keyboard Navigation

```css
/* Focus indicators */
:focus-visible {
    outline: 2px solid #00ff9d;
    outline-offset: 2px;
}

/* Skip links */
.skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: #00ff9d;
    color: #0d1117;
    padding: 8px;
    text-decoration: none;
}

.skip-link:focus {
    top: 0;
}
```

### Screen Reader Support

```html
<!-- ARIA labels for interactive elements -->
<button aria-label="View job details">
    <span class="icon">👁️</span>
</button>

<!-- Live regions for dynamic content -->
<div aria-live="polite" class="status-update">
    Processing complete
</div>
```

## Troubleshooting

### Issue: Colors not displaying correctly

**Solution**: Check browser compatibility and ensure custom CSS is loaded:
```python
st.markdown(custom_css, unsafe_allow_html=True)
```

### Issue: Animations not smooth

**Solution**: Enable hardware acceleration and reduce concurrent animations

### Issue: Mobile layout broken

**Solution**: Test responsive breakpoints and adjust grid layouts

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Main project documentation
- [src/webui/app.py](../../src/webui/app.py) - Main application
- [src/webui/agent_sessions_lab.py](../../src/webui/agent_sessions_lab.py) - Agent Sessions page
