#!/usr/bin/env python3
"""
ACHA CLI - AI Code Health Agent
"""
import argparse
import json
import sys
from pathlib import Path
from agents.analysis_agent import AnalysisAgent
from agents.refactor_agent import RefactorAgent


def analyze(args):
    """Run code analysis"""
    target_dir = args.target

    print(f"Analyzing code in: {target_dir}")

    # Run analysis
    agent = AnalysisAgent()
    try:
        result = agent.run(target_dir)
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Write results to reports/analysis.json
    output_path = reports_dir / "analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    # Print summary
    findings_count = len(result.get('findings', []))
    print(f"\nAnalysis complete!")
    print(f"Total findings: {findings_count}")
    print(f"Report written to: {output_path}")

    # Count findings by type
    finding_types = {}
    for finding in result.get('findings', []):
        ftype = finding.get('finding', 'unknown')
        finding_types[ftype] = finding_types.get(ftype, 0) + 1

    if finding_types:
        print("\nFindings by type:")
        for ftype, count in sorted(finding_types.items()):
            print(f"  {ftype}: {count}")

    return 0


def refactor(args):
    """Run code refactoring"""
    target_dir = args.target
    analysis_path = args.analysis

    print(f"Refactoring code in: {target_dir}")
    print(f"Using analysis from: {analysis_path}")

    # Run refactoring
    agent = RefactorAgent()
    try:
        patch_summary = agent.apply(target_dir, analysis_path)
    except Exception as e:
        print(f"Error during refactoring: {e}")
        return 1

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Write patch summary to reports/patch_summary.json
    summary_path = reports_dir / "patch_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(patch_summary, f, indent=2)

    # Print summary
    print(f"\nRefactoring complete!")
    print(f"Patch ID: {patch_summary['patch_id']}")
    print(f"Files touched: {len(patch_summary['files_touched'])}")
    print(f"Lines added: {patch_summary['lines_added']}")
    print(f"Lines removed: {patch_summary['lines_removed']}")
    print(f"Diff written to: dist/patch.diff")
    print(f"Summary written to: {summary_path}")

    if patch_summary.get('notes'):
        print("\nNotes:")
        for note in patch_summary['notes']:
            print(f"  - {note}")

    return 0


def validate(args):
    """Run validation"""
    print("validate command - not implemented yet")
    return 0


def export(args):
    """Export results"""
    print("export command - not implemented yet")
    return 0


def run(args):
    """Run full pipeline"""
    print("run command - not implemented yet")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog='acha',
        description='ACHA - AI Code Health Agent'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # analyze subcommand
    parser_analyze = subparsers.add_parser('analyze', help='Analyze code quality')
    parser_analyze.add_argument('--target', required=True, help='Target directory to analyze')
    parser_analyze.set_defaults(func=analyze)

    # refactor subcommand
    parser_refactor = subparsers.add_parser('refactor', help='Refactor code')
    parser_refactor.add_argument('--target', required=True, help='Target directory to refactor')
    parser_refactor.add_argument('--analysis', required=True, help='Path to analysis.json file')
    parser_refactor.set_defaults(func=refactor)

    # validate subcommand
    parser_validate = subparsers.add_parser('validate', help='Validate changes')
    parser_validate.set_defaults(func=validate)

    # export subcommand
    parser_export = subparsers.add_parser('export', help='Export reports')
    parser_export.set_defaults(func=export)

    # run subcommand
    parser_run = subparsers.add_parser('run', help='Run full pipeline')
    parser_run.set_defaults(func=run)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
