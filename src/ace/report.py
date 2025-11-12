"""Report generation - Workspace health map with inline assets.

Generates deterministic HTML report with no external dependencies (no CDN).
"""

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ace.uir import UnifiedIssue


def generate_health_map(
    findings: list[UnifiedIssue],
    receipts: list[dict[str, Any]] | None = None,
    output_path: Path | str = ".ace/health.html",
) -> str:
    """
    Generate workspace health map HTML report.

    Args:
        findings: List of UnifiedIssue findings
        receipts: Optional list of receipt dicts for time series
        output_path: Output file path

    Returns:
        Path to generated report

    Examples:
        >>> from ace.uir import create_uir
        >>> findings = [create_uir("test.py", 10, "RULE-1", "high", "msg", "", "")]
        >>> path = generate_health_map(findings, output_path="/tmp/health.html")
        >>> Path(path).exists()
        True
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Aggregate statistics
    stats = aggregate_statistics(findings, receipts)

    # Generate HTML
    html = render_health_map_html(stats)

    # Write deterministically
    output_path.write_text(html, encoding="utf-8")

    return str(output_path)


def aggregate_statistics(
    findings: list[UnifiedIssue],
    receipts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Aggregate findings into statistics.

    Args:
        findings: List of findings
        receipts: Optional receipts for time series

    Returns:
        Statistics dictionary
    """
    # By severity
    by_severity = defaultdict(int)
    for f in findings:
        by_severity[f.severity.value] += 1

    # By rule
    by_rule = defaultdict(int)
    for f in findings:
        by_rule[f.rule] += 1

    # By file
    by_file = defaultdict(int)
    for f in findings:
        by_file[f.file] += 1

    # By directory
    by_directory = defaultdict(int)
    for f in findings:
        dir_path = str(Path(f.file).parent)
        by_directory[dir_path] += 1

    # Time series from receipts
    time_series = []
    if receipts:
        # Group by timestamp
        by_timestamp = defaultdict(int)
        for receipt in receipts:
            timestamp = receipt.get("timestamp", "")
            if timestamp:
                # Truncate to minute
                ts_truncated = timestamp[:16]  # YYYY-MM-DDTHH:MM
                by_timestamp[ts_truncated] += 1

        time_series = [
            {"timestamp": ts, "count": count}
            for ts, count in sorted(by_timestamp.items())
        ]

    return {
        "total_findings": len(findings),
        "by_severity": dict(sorted(by_severity.items())),
        "by_rule": dict(sorted(by_rule.items(), key=lambda x: -x[1])[:20]),  # Top 20
        "by_file": dict(sorted(by_file.items(), key=lambda x: -x[1])[:20]),  # Top 20
        "by_directory": dict(sorted(by_directory.items(), key=lambda x: -x[1])[:20]),
        "time_series": time_series,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def render_health_map_html(stats: dict[str, Any]) -> str:
    """
    Render health map HTML with inline CSS/JS.

    Args:
        stats: Statistics dictionary

    Returns:
        HTML string
    """
    # Convert stats to JSON for inline embedding
    stats_json = json.dumps(stats, indent=2, sort_keys=True)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACE Workspace Health Map</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header .meta {{
            opacity: 0.9;
            font-size: 0.9em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .stat-card h3 {{
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }}
        .chart-card {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .chart-card h2 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.5em;
        }}
        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .bar-item {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .bar-label {{
            min-width: 200px;
            font-size: 0.9em;
            color: #666;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .bar-container {{
            flex: 1;
            height: 25px;
            background: #f0f0f0;
            border-radius: 5px;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
        }}
        .bar-value {{
            min-width: 40px;
            text-align: right;
            font-weight: bold;
            color: #667eea;
        }}
        .severity-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .severity-critical {{ background: #ff4444; color: white; }}
        .severity-high {{ background: #ff6b6b; color: white; }}
        .severity-medium {{ background: #ffa500; color: white; }}
        .severity-low {{ background: #4dabf7; color: white; }}
        .severity-info {{ background: #e0e0e0; color: #666; }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 ACE Workspace Health Map</h1>
            <div class="meta">
                Generated: {stats['generated_at']}<br>
                Total Findings: {stats['total_findings']}
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Findings</h3>
                <div class="value">{stats['total_findings']}</div>
            </div>
            <div class="stat-card">
                <h3>Files Affected</h3>
                <div class="value">{len(stats['by_file'])}</div>
            </div>
            <div class="stat-card">
                <h3>Directories</h3>
                <div class="value">{len(stats['by_directory'])}</div>
            </div>
            <div class="stat-card">
                <h3>Rule Types</h3>
                <div class="value">{len(stats['by_rule'])}</div>
            </div>
        </div>

        <div class="chart-card">
            <h2>📊 By Severity</h2>
            <div class="bar-chart">
                {render_severity_bars(stats['by_severity'], stats['total_findings'])}
            </div>
        </div>

        <div class="chart-card">
            <h2>📋 Top Rules</h2>
            <div class="bar-chart">
                {render_rule_bars(stats['by_rule'], stats['total_findings'])}
            </div>
        </div>

        <div class="chart-card">
            <h2>📁 Top Files</h2>
            <div class="bar-chart">
                {render_file_bars(stats['by_file'], stats['total_findings'])}
            </div>
        </div>

        <div class="chart-card">
            <h2>📂 Top Directories</h2>
            <div class="bar-chart">
                {render_directory_bars(stats['by_directory'], stats['total_findings'])}
            </div>
        </div>

        <div class="footer">
            Generated by ACE (Autonomous Code Editor) - v0.9.0
        </div>
    </div>

    <script>
        // Stats data embedded inline (no external requests)
        const stats = {stats_json};

        // Add interactivity if needed
        console.log('ACE Health Map loaded', stats);
    </script>
</body>
</html>"""

    return html


def render_severity_bars(by_severity: dict[str, int], total: int) -> str:
    """Render severity bars HTML."""
    if total == 0:
        return "<p>No findings</p>"

    severity_order = ["critical", "high", "medium", "low", "info"]
    bars = []

    for severity in severity_order:
        count = by_severity.get(severity, 0)
        if count == 0:
            continue

        percent = (count / total) * 100
        bars.append(f"""
            <div class="bar-item">
                <div class="bar-label">
                    <span class="severity-badge severity-{severity}">{severity}</span>
                </div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {percent}%"></div>
                </div>
                <div class="bar-value">{count}</div>
            </div>
        """)

    return "".join(bars)


def render_rule_bars(by_rule: dict[str, int], total: int) -> str:
    """Render rule bars HTML."""
    if not by_rule:
        return "<p>No rules</p>"

    bars = []
    max_count = max(by_rule.values())

    for rule, count in list(by_rule.items())[:10]:  # Top 10
        percent = (count / max_count) * 100
        bars.append(f"""
            <div class="bar-item">
                <div class="bar-label" title="{rule}">{rule}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {percent}%"></div>
                </div>
                <div class="bar-value">{count}</div>
            </div>
        """)

    return "".join(bars)


def render_file_bars(by_file: dict[str, int], total: int) -> str:
    """Render file bars HTML."""
    if not by_file:
        return "<p>No files</p>"

    bars = []
    max_count = max(by_file.values())

    for file, count in list(by_file.items())[:10]:  # Top 10
        percent = (count / max_count) * 100
        bars.append(f"""
            <div class="bar-item">
                <div class="bar-label" title="{file}">{file}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {percent}%"></div>
                </div>
                <div class="bar-value">{count}</div>
            </div>
        """)

    return "".join(bars)


def render_directory_bars(by_directory: dict[str, int], total: int) -> str:
    """Render directory bars HTML."""
    if not by_directory:
        return "<p>No directories</p>"

    bars = []
    max_count = max(by_directory.values())

    for directory, count in list(by_directory.items())[:10]:  # Top 10
        percent = (count / max_count) * 100
        bars.append(f"""
            <div class="bar-item">
                <div class="bar-label" title="{directory}">{directory}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {percent}%"></div>
                </div>
                <div class="bar-value">{count}</div>
            </div>
        """)

    return "".join(bars)


def compute_report_hash(html: str) -> str:
    """
    Compute deterministic hash of report.

    Args:
        html: HTML content

    Returns:
        SHA256 hash (hex string, first 16 chars)
    """
    return hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]
