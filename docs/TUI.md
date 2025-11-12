# ACE TUI Dashboard

Interactive terminal user interface for ACE with watch mode and real-time monitoring.

## Overview

The TUI Dashboard provides a rich, interactive terminal interface for monitoring code health, viewing findings, tracking risk, and managing ACE operations.

## Requirements

```bash
pip install textual
```

Or install ACE with TUI support:
```bash
pip install "acha-code-health[ace]"
```

## Launch

```bash
ace ui
```

## Layout

The dashboard is divided into panels:

```
┌─────────────────────────┬─────────────────────────┐
│  Watch                  │  Findings               │
│  📁 Watch Mode          │  🔍 Total: 23           │
│  ⚪ Not watching        │  🔴 Critical: 0         │
│  (press 'w' to start)   │  🟠 High: 5             │
│                         │  🟡 Medium: 12          │
├─────────────────────────┼─────────────────────────┤
│  Journal                │  Risk Heatmap           │
│  📔 Recent actions      │  🔥 Top risky files     │
│  • 2024-01-15 - apply   │  🔴 src/legacy.py: 89%  │
│  • 2024-01-15 - analyze │  🟠 src/utils.py: 67%   │
│                         │  🔵 src/main.py: 23%    │
└─────────────────────────┴─────────────────────────┘
│  Status: Ready                                    │
└───────────────────────────────────────────────────┘
```

## Key Bindings

| Key | Action | Description |
|-----|--------|-------------|
| `w` | Toggle Watch | Start/stop file watching with auto-analyze |
| `a` | Analyze | Run `ace analyze .` and refresh findings |
| `r` | Refresh | Refresh all panels with latest data |
| `h` | Health Report | Open `.ace/health.html` in browser |
| `q` | Quit | Exit the dashboard |

## Panels

### Watch Panel

Monitors file changes and triggers auto-analyze:
- Shows watch status (watching/not watching)
- Logs recent file change events
- Debounces rapid changes

### Journal Panel

Displays recent ACE actions from `.ace/journal/`:
- Apply operations
- Revert operations
- Analyze runs
- Shows timestamps

### Findings Panel

Current analysis results:
- Total findings count
- Breakdown by severity (critical, high, medium, low, info)
- Top 5 files by issue count

### Risk Heatmap Panel

Per-file risk scores from `.ace/metrics.json`:
- Top 10 riskiest files
- Risk percentage (0-100%)
- Color-coded by risk level

### Status Panel

Current status and last action:
- Ready, Running, Error states
- Last command executed
- Error messages if any

## Watch Mode

When watch mode is enabled (`w`):

1. **Monitors** file changes using debounced polling
2. **Auto-analyzes** when changes detected
3. **Updates** findings panel in real-time
4. **Logs** events to watch panel

Watch interval: ~5 seconds (configurable)

## Use Cases

### Interactive Development

```bash
# Launch TUI in a separate terminal
ace ui

# In your editor, make code changes
# TUI automatically detects and analyzes

# Press 'h' to view health report in browser
# Press 'q' to exit when done
```

### Code Review

```bash
# Launch TUI to monitor review session
ace ui

# Review findings and risk heatmap
# Run analysis with 'a' after changes
# Check journal for recent actions
```

### CI/CD Monitoring

```bash
# Launch TUI in watch mode
ace ui
# Press 'w' to enable watch

# Let it run in background terminal
# Monitor real-time as files change
```

## Configuration

Currently, the TUI uses default paths:
- Findings: `.ace/last_findings.json`
- Journal: `.ace/journal/`
- Metrics: `.ace/metrics.json`
- Health Report: `.ace/health.html`

## Troubleshooting

### Import Error

```
ImportError: No module named 'textual'
```

Solution:
```bash
pip install textual
```

### No Findings

If findings panel shows "No findings available":
1. Press `a` to run analysis
2. Or run `ace analyze .` in another terminal
3. Press `r` to refresh

### Health Report Not Found

If pressing `h` shows "No health report found":
```bash
ace report health
```

Then press `r` to refresh and `h` again.

## Example Session

```bash
# Launch dashboard
$ ace ui

# Dashboard opens with empty findings
# Press 'a' to analyze
[Status: Running analysis...]

# Wait for analysis to complete
[Status: Analysis complete]

# View findings in Findings panel
# View risk in Risk Heatmap panel

# Press 'w' to enable watch mode
[Watch: 🟢 Watching for changes...]

# Make code changes in editor
[Watch: • File changed: src/main.py]
[Status: Running analysis...]

# Press 'h' to open health report in browser
[Status: Opened health report in browser]

# Press 'q' to exit
```

## API

```python
from ace.tui.app import ACEDashboard, run_dashboard

# Run dashboard programmatically
run_dashboard()

# Or create custom dashboard
app = ACEDashboard()
app.run()
```
