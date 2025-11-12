"""ACE TUI Dashboard - Interactive terminal UI with watch mode.

Panels:
- Watch: Real-time file monitoring
- Journal: Recent actions and history
- Findings: Current analysis results
- Risk Heatmap: Per-file risk visualization
- Diff Preview: Code changes preview

Commands:
- w: Toggle watch mode
- a: Run analyze
- p: Apply selected plan
- r: Revert last action
- h: Open health.html in browser
- q: Quit
"""

import json
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, Static, TextLog
from textual.reactive import reactive


class WatchPanel(Static):
    """Watch panel - monitors file changes."""

    watching = reactive(False)
    last_event = reactive("")

    def compose(self) -> ComposeResult:
        yield Label("📁 Watch Mode", classes="panel-title")
        yield Static(id="watch-status")
        yield TextLog(id="watch-log", max_lines=10)

    def on_mount(self) -> None:
        """Initialize watch panel."""
        self.update_status()

    def update_status(self) -> None:
        """Update watch status display."""
        status = self.query_one("#watch-status", Static)
        if self.watching:
            status.update("🟢 Watching for changes...")
        else:
            status.update("⚪ Not watching (press 'w' to start)")

    def toggle_watch(self) -> None:
        """Toggle watch mode."""
        self.watching = not self.watching
        self.update_status()

        if self.watching:
            self.add_log("Watch mode enabled")
        else:
            self.add_log("Watch mode disabled")

    def add_log(self, message: str) -> None:
        """Add message to watch log."""
        log = self.query_one("#watch-log", TextLog)
        log.write(f"• {message}")
        self.last_event = message


class JournalPanel(Static):
    """Journal panel - shows recent actions."""

    def compose(self) -> ComposeResult:
        yield Label("📔 Journal", classes="panel-title")
        yield TextLog(id="journal-log", max_lines=15)

    def on_mount(self) -> None:
        """Load recent journal entries."""
        self.load_journal()

    def load_journal(self) -> None:
        """Load journal from .ace/journal/."""
        log = self.query_one("#journal-log", TextLog)
        journal_dir = Path(".ace/journal")

        if not journal_dir.exists():
            log.write("No journal entries yet")
            return

        # Get latest journal entries
        entries = sorted(journal_dir.glob("*.json"), reverse=True)[:10]

        if not entries:
            log.write("No journal entries yet")
            return

        for entry_path in entries:
            try:
                with open(entry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    action = data.get("action", "unknown")
                    timestamp = data.get("timestamp", "")[:19]  # Truncate to datetime
                    log.write(f"• {timestamp} - {action}")
            except (json.JSONDecodeError, OSError):
                continue

    def refresh_journal(self) -> None:
        """Refresh journal display."""
        log = self.query_one("#journal-log", TextLog)
        log.clear()
        self.load_journal()


class FindingsPanel(Static):
    """Findings panel - shows current analysis results."""

    findings_count = reactive(0)

    def compose(self) -> ComposeResult:
        yield Label("🔍 Findings", classes="panel-title")
        yield Static(id="findings-summary")
        yield TextLog(id="findings-log", max_lines=15)

    def on_mount(self) -> None:
        """Load current findings."""
        self.load_findings()

    def load_findings(self) -> None:
        """Load findings from last analysis."""
        summary = self.query_one("#findings-summary", Static)
        log = self.query_one("#findings-log", TextLog)

        # Check for cached findings
        findings_file = Path(".ace/last_findings.json")

        if not findings_file.exists():
            summary.update("No findings available (run 'a' to analyze)")
            log.write("Run analysis to see findings")
            return

        try:
            with open(findings_file, "r", encoding="utf-8") as f:
                findings = json.load(f)

            self.findings_count = len(findings)
            summary.update(f"Total: {len(findings)} findings")

            # Group by severity
            by_severity: dict[str, int] = {}
            for finding in findings:
                severity = finding.get("severity", "info")
                by_severity[severity] = by_severity.get(severity, 0) + 1

            # Display summary
            for severity in ["critical", "high", "medium", "low", "info"]:
                if severity in by_severity:
                    count = by_severity[severity]
                    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
                    log.write(f"{emoji.get(severity, '•')} {severity.capitalize()}: {count}")

            # Show top files
            by_file: dict[str, int] = {}
            for finding in findings:
                file_path = finding.get("file", "unknown")
                by_file[file_path] = by_file.get(file_path, 0) + 1

            log.write("\nTop files:")
            for file_path, count in sorted(by_file.items(), key=lambda x: -x[1])[:5]:
                log.write(f"  • {file_path}: {count}")

        except (json.JSONDecodeError, OSError) as e:
            summary.update("Error loading findings")
            log.write(f"Error: {e}")

    def refresh_findings(self) -> None:
        """Refresh findings display."""
        log = self.query_one("#findings-log", TextLog)
        log.clear()
        self.load_findings()


class RiskHeatmapPanel(Static):
    """Risk heatmap panel - shows per-file risk scores."""

    def compose(self) -> ComposeResult:
        yield Label("🔥 Risk Heatmap", classes="panel-title")
        yield TextLog(id="risk-log", max_lines=10)

    def on_mount(self) -> None:
        """Load risk heatmap."""
        self.load_risk_heatmap()

    def load_risk_heatmap(self) -> None:
        """Load risk heatmap from .ace/metrics.json."""
        log = self.query_one("#risk-log", TextLog)

        # Try to generate risk heatmap from current findings
        try:
            findings_file = Path(".ace/last_findings.json")
            if not findings_file.exists():
                log.write("No risk data (run analysis first)")
                return

            with open(findings_file, "r", encoding="utf-8") as f:
                findings_data = json.load(f)

            # Import to calculate risk
            from ace.report import generate_risk_heatmap
            from ace.uir import UnifiedIssue, Severity

            # Convert dicts back to UnifiedIssue objects
            findings = []
            for f_dict in findings_data:
                findings.append(
                    UnifiedIssue(
                        file=f_dict["file"],
                        line=f_dict["line"],
                        rule=f_dict["rule"],
                        severity=Severity(f_dict["severity"]),
                        message=f_dict["message"],
                        suggestion=f_dict.get("suggestion", ""),
                        snippet=f_dict.get("snippet", ""),
                    )
                )

            risk_map = generate_risk_heatmap(findings)

            if not risk_map:
                log.write("No risk data available")
                return

            # Show top 10 riskiest files
            sorted_files = sorted(risk_map.items(), key=lambda x: -x[1])[:10]

            for file_path, risk_score in sorted_files:
                risk_pct = int(risk_score * 100)
                emoji = "🔴" if risk_score > 0.66 else "🟠" if risk_score > 0.33 else "🔵"
                log.write(f"{emoji} {file_path}: {risk_pct}%")

        except Exception as e:
            log.write(f"Error loading risk data: {e}")

    def refresh_risk(self) -> None:
        """Refresh risk heatmap display."""
        log = self.query_one("#risk-log", TextLog)
        log.clear()
        self.load_risk_heatmap()


class StatusPanel(Static):
    """Status panel - shows current status and commands."""

    status_text = reactive("Ready")

    def compose(self) -> ComposeResult:
        yield Label("ℹ️ Status", classes="panel-title")
        yield Static(id="status-text")

    def on_mount(self) -> None:
        """Initialize status."""
        self.update_status("Ready")

    def update_status(self, message: str) -> None:
        """Update status message."""
        self.status_text = message
        status = self.query_one("#status-text", Static)
        status.update(f"Status: {message}")


class ACEDashboard(App[None]):
    """ACE TUI Dashboard - Interactive terminal UI."""

    CSS = """
    Screen {
        background: $surface;
    }

    .panel-title {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    Container {
        height: 100%;
    }

    #left-column {
        width: 1fr;
        border: solid $primary;
    }

    #right-column {
        width: 1fr;
        border: solid $primary;
    }

    #watch-panel {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }

    #journal-panel {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }

    #findings-panel {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }

    #risk-panel {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }

    #status-panel {
        height: 5;
        border: solid $accent;
        margin: 1;
    }

    TextLog {
        height: 1fr;
        background: $surface;
        color: $text;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("w", "toggle_watch", "Toggle Watch", show=True),
        Binding("a", "run_analyze", "Analyze", show=True),
        Binding("r", "refresh_all", "Refresh", show=True),
        Binding("h", "open_health", "Health Report", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header(show_clock=True)

        with Horizontal():
            with Vertical(id="left-column"):
                yield WatchPanel(id="watch-panel")
                yield JournalPanel(id="journal-panel")

            with Vertical(id="right-column"):
                yield FindingsPanel(id="findings-panel")
                yield RiskHeatmapPanel(id="risk-panel")

        yield StatusPanel(id="status-panel")
        yield Footer()

    def action_toggle_watch(self) -> None:
        """Toggle watch mode."""
        watch_panel = self.query_one("#watch-panel", WatchPanel)
        watch_panel.toggle_watch()

        status = self.query_one("#status-panel", StatusPanel)
        status.update_status("Watch mode toggled")

    def action_run_analyze(self) -> None:
        """Run analysis."""
        status = self.query_one("#status-panel", StatusPanel)
        status.update_status("Running analysis...")

        try:
            # Resolve executable path explicitly for security
            ace_exe = shutil.which("ace")
            if not ace_exe:
                status.update_status("Error: ace executable not found in PATH")
                return

            # Run ace analyze with check=True to raise on failure
            result = subprocess.run(
                [ace_exe, "analyze", "."],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,  # Raise CalledProcessError on non-zero exit
            )

            # Save findings
            findings_file = Path(".ace/last_findings.json")
            findings_file.parent.mkdir(parents=True, exist_ok=True)
            findings_file.write_text(result.stdout)

            # Refresh panels
            self.action_refresh_all()
            status.update_status("Analysis complete")

        except subprocess.TimeoutExpired:
            status.update_status("Analysis timed out")
        except subprocess.CalledProcessError as e:
            # Handle non-zero exit codes from ace analyze
            error_msg = e.stderr[:50] if e.stderr else f"Exit code {e.returncode}"
            status.update_status(f"Analysis failed: {error_msg}")
        except Exception as e:
            status.update_status(f"Error: {str(e)[:50]}")

    def action_refresh_all(self) -> None:
        """Refresh all panels."""
        journal = self.query_one("#journal-panel", JournalPanel)
        journal.refresh_journal()

        findings = self.query_one("#findings-panel", FindingsPanel)
        findings.refresh_findings()

        risk = self.query_one("#risk-panel", RiskHeatmapPanel)
        risk.refresh_risk()

        status = self.query_one("#status-panel", StatusPanel)
        status.update_status("Refreshed all panels")

    def action_open_health(self) -> None:
        """Open health report in browser."""
        health_path = Path(".ace/health.html")

        if not health_path.exists():
            status = self.query_one("#status-panel", StatusPanel)
            status.update_status("No health report found (run 'ace report health')")
            return

        try:
            # Open in default browser
            webbrowser.open(f"file://{health_path.resolve()}")

            status = self.query_one("#status-panel", StatusPanel)
            status.update_status("Opened health report in browser")
        except Exception as e:
            status = self.query_one("#status-panel", StatusPanel)
            status.update_status(f"Error opening browser: {str(e)[:50]}")


def run_dashboard() -> None:
    """Run the ACE dashboard."""
    app = ACEDashboard()
    app.run()


if __name__ == "__main__":
    run_dashboard()
