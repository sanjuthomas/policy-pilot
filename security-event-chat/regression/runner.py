#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

from regression.assertions import evaluate_expectations
from regression.models import (
    CaseResult,
    RegressionCase,
    RegressionSuite,
    SuiteResult,
)
from regression.seed import (
    fetch_context,
    run_seed,
    wait_for_index,
)

logger = logging.getLogger(__name__)

DEFAULT_QUESTIONS = Path(__file__).resolve().parent / "questions.yaml"


def load_suite(path: Path) -> RegressionSuite:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RegressionSuite.model_validate(raw)


def render_question(question: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise KeyError(key)
        return context[key]

    return re.sub(r"\{([a-z_]+)\}", replace, question)


def filter_cases(
    cases: list[RegressionCase],
    *,
    mode: str | None,
    tags: set[str] | None,
    case_ids: set[str] | None,
) -> list[RegressionCase]:
    selected = cases
    if mode and mode != "all":
        selected = [case for case in selected if case.mode == mode]
    if tags:
        selected = [case for case in selected if tags.intersection(case.tags)]
    if case_ids:
        selected = [case for case in selected if case.id in case_ids]
    return selected


def ask_chat(
    client: httpx.Client,
    chat_url: str,
    case: RegressionCase,
    question: str,
) -> dict:
    response = client.post(
        f"{chat_url.rstrip('/')}/api/chat",
        json={"message": question, "mode": case.mode, "history": []},
        timeout=600.0,
    )
    response.raise_for_status()
    return response.json()


def run_case(
    client: httpx.Client,
    chat_url: str,
    case: RegressionCase,
    context: dict[str, str],
) -> CaseResult:
    try:
        question = render_question(case.question, context)
    except KeyError as exc:
        if case.expect.skip_if_missing_context:
            return CaseResult(
                id=case.id,
                mode=case.mode,
                question=case.question,
                passed=False,
                skipped=True,
                reason=f"missing context key: {exc.args[0]}",
                tags=case.tags,
            )
        return CaseResult(
            id=case.id,
            mode=case.mode,
            question=case.question,
            passed=False,
            reason=f"missing context key: {exc.args[0]}",
            tags=case.tags,
        )

    for key in case.expect.requires_context:
        if key not in context:
            if case.expect.skip_if_missing_context:
                return CaseResult(
                    id=case.id,
                    mode=case.mode,
                    question=question,
                    passed=False,
                    skipped=True,
                    reason=f"missing required context: {key}",
                    tags=case.tags,
                )
            return CaseResult(
                id=case.id,
                mode=case.mode,
                question=question,
                passed=False,
                reason=f"missing required context: {key}",
                tags=case.tags,
            )

    try:
        payload = ask_chat(client, chat_url, case, question)
    except Exception as exc:  # noqa: BLE001
        return CaseResult(
            id=case.id,
            mode=case.mode,
            question=question,
            passed=False,
            reason=f"chat request failed: {exc}",
            tags=case.tags,
        )

    answer = payload.get("answer") or ""
    sources = payload.get("sources") or []
    graph_rows = payload.get("graph_rows") or []
    passed, reason = evaluate_expectations(
        case.expect,
        answer=answer,
        sources=sources,
        graph_rows=graph_rows,
        cypher=payload.get("cypher"),
    )

    preview = answer.strip().replace("\n", " ")
    if len(preview) > 240:
        preview = preview[:237] + "..."

    return CaseResult(
        id=case.id,
        mode=case.mode,
        question=question,
        passed=passed,
        reason=reason,
        answer_preview=preview,
        sources=len(sources),
        graph_rows=len(graph_rows),
        retrieval_ms=payload.get("retrieval_ms"),
        generation_ms=payload.get("generation_ms"),
        tags=case.tags,
    )


def print_summary(result: SuiteResult) -> None:
    print("\n=== Chat regression summary ===")
    print(f"passed={result.passed} failed={result.failed} skipped={result.skipped}")
    for case in result.cases:
        status = "PASS" if case.passed else ("SKIP" if case.skipped else "FAIL")
        print(f"[{status}] {case.id} ({case.mode})")
        if not case.passed:
            print(f"       reason: {case.reason}")
            if case.answer_preview:
                print(f"       answer: {case.answer_preview}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run security-event-chat regression suite")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--chat-url", default="http://localhost:8092")
    parser.add_argument("--harness-url", default="http://localhost:8091")
    parser.add_argument("--ilm-url", default="http://localhost:8000")
    parser.add_argument("--payment-url", default="http://localhost:8093")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--qdrant-collection", default="ssi_search_index")
    parser.add_argument("--mode", choices=["events", "instructions", "payments", "all"], default="all")
    parser.add_argument("--tags", default="", help="Comma-separated tag filter")
    parser.add_argument("--ids", default="", help="Comma-separated case id filter")
    parser.add_argument("--seed", action="store_true", help="Run harness seed steps before tests")
    parser.add_argument("--no-wait", action="store_true", help="Skip waiting for ETL index after seed")
    parser.add_argument("--report", type=Path, help="Write JSON report to this path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    suite = load_suite(args.questions)
    tag_filter = {tag.strip() for tag in args.tags.split(",") if tag.strip()} or None
    id_filter = {item.strip() for item in args.ids.split(",") if item.strip()} or None
    cases = filter_cases(suite.cases, mode=args.mode, tags=tag_filter, case_ids=id_filter)

    if args.seed and suite.seed.steps:
        logger.info("running %s seed step(s)", len(suite.seed.steps))
        run_seed(args.harness_url, suite.seed)
        if not args.no_wait:
            wait_for_index(
                harness_url=args.harness_url,
                qdrant_url=args.qdrant_url,
                qdrant_collection=args.qdrant_collection,
                min_security_events=suite.seed.wait.min_security_events,
                min_qdrant_points=suite.seed.wait.min_qdrant_points,
                timeout_seconds=suite.seed.wait.timeout_seconds,
                poll_interval_seconds=suite.seed.wait.poll_interval_seconds,
            )

    context = fetch_context(ilm_url=args.ilm_url, payment_url=args.payment_url)
    logger.info("resolved context keys: %s", sorted(context))

    result = SuiteResult(context=context)
    started = time.perf_counter()

    with httpx.Client() as client:
        health = client.get(f"{args.chat_url.rstrip('/')}/health", timeout=15.0)
        health.raise_for_status()

        for index, case in enumerate(cases, start=1):
            logger.info("[%s/%s] %s", index, len(cases), case.id)
            case_result = run_case(client, args.chat_url, case, context)
            result.cases.append(case_result)
            if case_result.skipped:
                result.skipped += 1
            elif case_result.passed:
                result.passed += 1
            else:
                result.failed += 1

    elapsed = time.perf_counter() - started
    print_summary(result)
    print(f"\nCompleted {len(cases)} case(s) in {elapsed:.1f}s")

    if args.report:
        payload = result.to_dict()
        payload["elapsed_seconds"] = round(elapsed, 2)
        args.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Report written to {args.report}")

    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
