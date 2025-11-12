"""Report generation - Workspace health map with inline assets.

Generates deterministic HTML report with no external dependencies (no CDN).

v2 enhancements:
- Per-file risk heatmap (revert_rate + churn + slow_rule weights)
- Mini-timeseries persistence to .ace/metrics.json
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
    Generate workspace health map HTML report (v2 with risk heatmap).

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

    # v2: Generate risk heatmap
    risk_map = generate_risk_heatmap(findings)

    # v2: Persist metrics
    persist_metrics(findings, risk_map)

    # Aggregate statistics
    stats = aggregate_statistics(findings, receipts)

    # v2: Add risk map to stats
    stats["risk_map"] = risk_map

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

        <div class="chart-card">
            <h2>🔥 Risk Heatmap</h2>
            <div class="bar-chart">
                {render_risk_heatmap_bars(stats.get('risk_map', {}))}
            </div>
        </div>

        <div class="footer">
            Generated by ACE (Autonomous Code Editor) - v1.7.0
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


def render_risk_heatmap_bars(risk_map: dict[str, float]) -> str:
    """Render risk heatmap bars HTML (v2)."""
    if not risk_map:
        return "<p>No risk data available</p>"

    bars = []

    # Sort by risk score descending
    sorted_files = sorted(risk_map.items(), key=lambda x: -x[1])

    for file_path, risk_score in sorted_files[:15]:  # Top 15 riskiest files
        percent = risk_score * 100  # Already 0-1, convert to 0-100%

        # Color gradient based on risk: green -> yellow -> red
        if risk_score < 0.33:
            color = "#4dabf7"  # Low risk - blue
        elif risk_score < 0.66:
            color = "#ffa500"  # Medium risk - orange
        else:
            color = "#ff4444"  # High risk - red

        bars.append(f"""
            <div class="bar-item">
                <div class="bar-label" title="{file_path}">{file_path}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {percent}%; background: {color};"></div>
                </div>
                <div class="bar-value">{risk_score:.2f}</div>
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


# v2: Risk Heatmap Functions


def calculate_file_risk(
    file_path: str,
    findings: list[UnifiedIssue],
    learn_data: dict[str, Any] | None = None,
    telemetry_data: dict[str, Any] | None = None,
) -> float:
    """
    Calculate risk score for a file (v2 heatmap).

    Risk = revert_rate_weight + churn_weight + slow_rule_weight

    Args:
        file_path: File path
        findings: All findings (used to count issues per file)
        learn_data: Optional learning data for revert rates
        telemetry_data: Optional telemetry data for slow rules

    Returns:
        Risk score (0.0 - 1.0)
    """
    risk = 0.0

    # Weight 1: Revert rate (0-0.4)
    if learn_data and "rules" in learn_data:
        # Get rules that have issues in this file
        file_findings = [f for f in findings if f.file == file_path]
        file_rules = set(f.rule for f in file_findings)

        revert_rates = []
        for rule_id in file_rules:
            if rule_id in learn_data["rules"]:
                rule_stats = learn_data["rules"][rule_id]
                applied = rule_stats.get("applied", 0)
                reverted = rule_stats.get("reverted", 0)
                total = applied + reverted
                if total > 0:
                    revert_rates.append(reverted / total)

        if revert_rates:
            risk += (sum(revert_rates) / len(revert_rates)) * 0.4

    # Weight 2: Churn (number of issues) (0-0.3)
    file_issue_count = len([f for f in findings if f.file == file_path])
    max_issues = 20  # Normalize to 20 issues = max churn
    risk += min(file_issue_count / max_issues, 1.0) * 0.3

    # Weight 3: Slow rules (0-0.3)
    if telemetry_data and "per_rule_avg_ms" in telemetry_data:
        file_findings = [f for f in findings if f.file == file_path]
        file_rules = set(f.rule for f in file_findings)

        slow_scores = []
        for rule_id in file_rules:
            if rule_id in telemetry_data["per_rule_avg_ms"]:
                avg_ms = telemetry_data["per_rule_avg_ms"][rule_id]
                # Normalize: 100ms = 0.5, 200ms+ = 1.0
                slow_scores.append(min(avg_ms / 200.0, 1.0))

        if slow_scores:
            risk += (sum(slow_scores) / len(slow_scores)) * 0.3

    return min(risk, 1.0)  # Cap at 1.0


def generate_risk_heatmap(
    findings: list[UnifiedIssue],
    learn_path: Path = Path(".ace/learn.json"),
    telemetry_path: Path = Path(".ace/telemetry.jsonl"),
) -> dict[str, float]:
    """
    Generate per-file risk heatmap.

    Args:
        findings: List of findings
        learn_path: Path to learning data
        telemetry_path: Path to telemetry data

    Returns:
        Dictionary mapping file_path -> risk_score
    """
    # Load learning data
    learn_data = None
    if learn_path.exists():
        try:
            with open(learn_path, "r", encoding="utf-8") as f:
                learn_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Load telemetry data (aggregate to stats dict)
    telemetry_data = None
    if telemetry_path.exists():
        try:
            from ace.telemetry import Telemetry

            telem = Telemetry(telemetry_path)
            stats = telem.load_stats()
            telemetry_data = {
                "per_rule_avg_ms": stats.per_rule_avg_ms,
                "per_rule_p95_ms": stats.per_rule_p95_ms,
            }
        except Exception:
            pass

    # Calculate risk per file
    files = set(f.file for f in findings)
    risk_map = {}

    for file_path in files:
        risk = calculate_file_risk(file_path, findings, learn_data, telemetry_data)
        risk_map[file_path] = risk

    return risk_map


def persist_metrics(
    findings: list[UnifiedIssue],
    risk_map: dict[str, float],
    metrics_path: Path = Path(".ace/metrics.json"),
) -> None:
    """
    Persist metrics mini-timeseries to .ace/metrics.json.

    Args:
        findings: List of findings
        risk_map: Per-file risk scores
        metrics_path: Path to metrics file
    """
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing metrics
    history = []
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            history = []

    # Add new entry
    timestamp = datetime.now(UTC).isoformat()
    entry = {
        "timestamp": timestamp,
        "total_findings": len(findings),
        "files_affected": len(set(f.file for f in findings)),
        "avg_risk": sum(risk_map.values()) / len(risk_map) if risk_map else 0.0,
        "max_risk": max(risk_map.values()) if risk_map else 0.0,
    }
    history.append(entry)

    # Keep only last 100 entries
    history = history[-100:]

    # Write deterministically
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, sort_keys=True)
        f.write("\n")
