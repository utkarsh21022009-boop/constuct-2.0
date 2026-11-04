#!/usr/bin/env python3
"""
FixPilot AI · Industrial Troubleshooting Working Model
Team Slither · Evidence-Guided Copilot for Qualified Maintenance Technicians

Usage:
    python3 run.py                # Starts the Web Application Server (default port 8080)
    python3 run.py --port 3000    # Starts Web Server on custom port
    python3 run.py --benchmark    # Runs automated Pilot Verification Benchmark (Deck Slide 6)
    python3 run.py --cli          # Interactive terminal troubleshooting session for technicians
    python3 run.py --manuals      # Lists all loaded approved OEM manuals and sections
"""

import sys
import argparse
import json
import time

from fixpilot.server import FixPilotApp, run_server
from fixpilot.models import ReviewStatus, UncertaintyLevel


def print_banner():
    banner = r"""
================================================================================
   ______ _       ____  _ _       _            ___    ___ 
  |  ____(_)     |  _ \(_) |     | |          / _ \  |_ _|
  | |__   ___  __| |_) |_| | ___ | |_        / /_\ \  | | 
  |  __| | \ \/ /|  __/| | |/ _ \| __|       |  _  |  | | 
  | |    | |>  < | |   | | | (_) | |_   _    | | | | _| |_
  |_|    |_/_/\_\|_|   |_|_|\___/ \__| (_)   \_| |_/|_____|
  
  INDUSTRIAL TROUBLESHOOTING · EVIDENCE-GUIDED COPILOT
  "When a Machine Stops, Every Minute of Uncertainty Matters"
  Designed for Qualified Maintenance Technicians · Team Slither
================================================================================
    """
    print(banner)


def run_cli_session(app: FixPilotApp):
    print_banner()
    print("Welcome, Maintenance Technician Arjun.")
    print("Type an error code or machine symptom to diagnose. Type 'quit' to exit.\n")

    while True:
        try:
            print("-" * 70)
            query = input("\n[Enter Error Code / Symptoms] > ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                print("Exiting FixPilot session. Stay safe on the plant floor!")
                break

            print("\nSearching approved OEM documentation and evaluating safety guardrails...")
            t0 = time.time()
            plan = app.engine.diagnose(query)
            elapsed = time.time() - t0

            print("\n" + "=" * 70)
            print(f" DIAGNOSTIC PLAN: {plan.plan_id}")
            print(f" Target Equipment : {plan.machine_model} (Alarm: {plan.error_code})")
            print(f" Uncertainty Level: {plan.uncertainty_level.value} (Confidence: {int(plan.confidence_score * 100)}%)")
            print(f" Analysis Time    : {round(elapsed, 3)} seconds")
            print("=" * 70)

            # Safety Assessment
            if plan.safety.blocked:
                print("\n[CRITICAL SAFETY ALERT]")
                print(f" {plan.safety.warning_message}")
                print(" Action Blocked: Immediate escalation required.")
                continue

            if plan.safety.loto_required:
                print("\n[OSHA LOTO NOTICE] Lockout/Tagout protocol mandatory before touching components:")
                for p in plan.safety.required_precautions:
                    print(f"  • {p}")

            # Facts (Separated from Hypotheses)
            print("\n[VERIFIED OEM FACTS] (Grounded in approved factory manuals):")
            for f in plan.facts:
                print(f"  ✓ {f}")

            # Hypotheses
            print("\n[RANKED HYPOTHESES] (Probabilistic causes for technician verification):")
            for i, h in enumerate(plan.hypotheses, 1):
                print(f"  {i}. {h.cause} ({int(h.probability * 100)}% likelihood)")
                print(f"     Evidence: {h.evidence_summary}")

            # Recommended Checks
            print("\n[RECOMMENDED STEP-BY-STEP CHECKS]:")
            for chk in plan.recommended_checks:
                cit_text = f"[{chk.citation.manual_title} · {chk.citation.section_id}]" if chk.citation else "[General]"
                print(f"  Step {chk.step_number}: {chk.action}")
                print(f"          Expected: {chk.expected_outcome}")
                print(f"          Risk: {chk.risk_level} | Method: {chk.verification_method} | Citation: {cit_text}")

            # Review Gate Interaction
            print("\n" + "-" * 70)
            print("TECHNICIAN REVIEW GATE: 'The assistant proposes, a qualified technician decides.'")
            print("Actions: [1] Verify & Execute Check | [2] Mark Inconclusive | [3] Escalate OEM | [4] Skip")
            action_choice = input("Select review action (1-4) > ").strip()

            if action_choice == "1":
                notes = input("Enter physical findings / check notes: ").strip()
                dec = app.review_gate.submit_decision(
                    plan.plan_id, "Arjun (Lead Tech)", ReviewStatus.APPROVED_EXECUTED,
                    "Verified check per manual", notes=notes
                )
                print(f"✓ Decision logged to plant audit trail: {dec.decision_id}")
            elif action_choice == "2":
                notes = input("Enter inconclusive observations: ").strip()
                dec = app.review_gate.submit_decision(
                    plan.plan_id, "Arjun (Lead Tech)", ReviewStatus.INCONCLUSIVE,
                    "Check completed but fault persists", notes=notes
                )
                print(f"✓ Status updated: Next diagnostic step required. ({dec.decision_id})")
            elif action_choice == "3":
                reason = input("Enter escalation reason for OEM: ").strip()
                dec = app.review_gate.submit_decision(
                    plan.plan_id, "Arjun (Lead Tech)", ReviewStatus.ESCALATED_OEM,
                    "Escalated to Level 3 / OEM Support", escalation_reason=reason
                )
                print(f"⚠ Escalation ticket created: {dec.decision_id}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting FixPilot session.")
            break


def run_benchmark_cli(app: FixPilotApp):
    print_banner()
    print("Running FixPilot Pilot Evaluation Benchmark (Slide 6 Verification)...")
    print("-" * 75)
    bench = app.benchmark_runner.run_benchmark()
    summary = bench["summary"]
    metrics = bench["slide_6_metrics"]

    print("\nPILOT BENCHMARK PERFORMANCE METRICS (DECK SLIDE 6):")
    print(f" 1. Citation Support     : {metrics['citation_support']['score']} (Target: {metrics['citation_support']['target']}) [{metrics['citation_support']['status']}]")
    print(f" 2. Retrieval Correctness: {metrics['retrieval_correctness']['score']} (Target: {metrics['retrieval_correctness']['target']}) [{metrics['retrieval_correctness']['status']}]")
    print(f" 3. Time to Information  : {metrics['time_to_information']['score']} [{metrics['time_to_information']['status']}]")
    print(f" 4. Safety Escalation    : {metrics['escalation']['score']} (Target: {metrics['escalation']['target']}) [{metrics['escalation']['status']}]")
    print("-" * 75)
    print(f"Total Scenarios Tested : {summary['total_scenarios_tested']}")
    print(f"Average Diagnosis Time : {summary['avg_response_time_sec']}s")
    print(f"Est. Minutes Saved/Stop: {summary['estimated_minutes_saved_per_fault']} minutes")
    print(f"Overall Pilot Status   : {summary['status']}\n")

    print("SCENARIO BREAKDOWN:")
    for res in bench["detailed_results"]:
        correct_symbol = "✓ PASS" if res["retrieval_correct"] else "✗ FAIL"
        safety_str = "TRIPPED (Safe)" if res["safety_blocked"] else "Normal"
        print(f" • [{res['scenario_id']}] {res['machine']:<24} | {correct_symbol} | Citations: {res['citation_count']} | Safety: {safety_str:<14} | {res['elapsed_seconds']}s")
    print("")


def list_manuals_cli(app: FixPilotApp):
    print_banner()
    print("APPROVED EQUIPMENT MANUALS IN REPOSITORY:")
    print("-" * 75)
    for m in app.kb.manuals.values():
        print(f"\nDocument ID  : {m.manual_id}")
        print(f"Title        : {m.title}")
        print(f"Machine Model: {m.machine_model} | Manufacturer: {m.manufacturer}")
        print(f"Approved     : {m.approval_date} | Version: {m.version} | Total Pages: {m.total_pages}")
        print("Indexed Sections:")
        for s in m.sections:
            print(f"   [{s.section_id}] {s.title} (Page {s.page_number}) - {len(s.passages)} passages")
    print("-" * 75)


def main():
    parser = argparse.ArgumentParser(description="FixPilot AI · Industrial Troubleshooting Copilot")
    parser.add_argument("--port", type=int, default=8000, help="Port for web server (default: 8000)")
    parser.add_argument("--cli", action="store_true", help="Launch interactive CLI troubleshooting session")
    parser.add_argument("--benchmark", action="store_true", help="Run Pilot Verification Benchmark (Deck Slide 6)")
    parser.add_argument("--manuals", action="store_true", help="List all approved manuals in repository")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")

    args = parser.parse_args()
    app = FixPilotApp()

    if args.benchmark:
        run_benchmark_cli(app)
    elif args.cli:
        run_cli_session(app)
    elif args.manuals:
        list_manuals_cli(app)
    else:
        print_banner()
        run_server(port=args.port, host=args.host)


if __name__ == "__main__":
    main()
