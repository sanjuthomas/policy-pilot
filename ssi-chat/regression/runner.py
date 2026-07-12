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

from regression.api_smoke import print_smoke_summary, run_api_smoke, smoke_to_dict
from regression.assertions import evaluate_expectations
from regression.auth_helpers import compliance_auth_headers
from regression.eval_metrics import (
    CaseQualityScores,
    evaluate_case_quality,
    summarize_suite_quality,
)
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
DEFAULT_GOLDEN = Path(__file__).resolve().parent / "eval_golden.yaml"


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
    retrieval: set[str] | None,
) -> list[RegressionCase]:
    selected = cases
    if mode and mode != "all":
        selected = [case for case in selected if case.mode == mode]
    if tags:
        selected = [case for case in selected if tags.intersection(case.tags)]
    if case_ids:
        selected = [case for case in selected if case.id in case_ids]
    if retrieval:
        selected = [case for case in selected if case.retrieval in retrieval]
    return selected


def ask_chat(
    client: httpx.Client,
    chat_url: str,
    case: RegressionCase,
    question: str,
    *,
    auth_headers: dict[str, str],
) -> dict:
    response = client.post(
        f"{chat_url.rstrip('/')}/api/chat",
        json={"message": question, "mode": case.mode, "history": []},
        headers=auth_headers,
        timeout=600.0,
    )
    response.raise_for_status()
    return response.json()


def _quality_gate_enabled(expect) -> bool:
    return bool(
        expect.require_routing
        or expect.require_entity_recall
        or expect.routing_path
        or expect.cypher_class
        or expect.answer_synthesis
        or expect.source_channels_any
        or expect.max_generation_ms is not None
        or expect.min_groundedness is not None
        or expect.min_faithfulness is not None
    )


def run_case(
    client: httpx.Client,
    chat_url: str,
    case: RegressionCase,
    context: dict[str, str],
    *,
    auth_headers: dict[str, str],
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
                retrieval=case.retrieval,
            )
        return CaseResult(
            id=case.id,
            mode=case.mode,
            question=case.question,
            passed=False,
            reason=f"missing context key: {exc.args[0]}",
            tags=case.tags,
            retrieval=case.retrieval,
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
                    retrieval=case.retrieval,
                )
            return CaseResult(
                id=case.id,
                mode=case.mode,
                question=question,
                passed=False,
                reason=f"missing required context: {key}",
                tags=case.tags,
                retrieval=case.retrieval,
            )

    try:
        payload = ask_chat(client, chat_url, case, question, auth_headers=auth_headers)
    except Exception as exc:  # noqa: BLE001
        return CaseResult(
            id=case.id,
            mode=case.mode,
            question=question,
            passed=False,
            reason=f"chat request failed: {exc}",
            tags=case.tags,
            retrieval=case.retrieval,
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

    quality = evaluate_case_quality(
        retrieval=case.retrieval,
        expect=case.expect,
        question=question,
        answer=answer,
        sources=sources,
        graph_rows=graph_rows,
        routing=payload.get("routing"),
        generation_ms=payload.get("generation_ms"),
    )
    if passed and _quality_gate_enabled(case.expect) and not quality.passed:
        passed = False
        reason = quality.failures[0] if quality.failures else "quality gate failed"

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
        retrieval=case.retrieval,
        quality=quality.to_dict(),
    )


def print_quality_summary(result: SuiteResult) -> None:
    from dataclasses import fields

    allowed = {f.name for f in fields(CaseQualityScores)}
    scored = []
    for case in result.cases:
        if not case.quality or not case.retrieval or case.skipped:
            continue
        payload = {k: v for k, v in case.quality.items() if k in allowed}
        scored.append((case.retrieval, CaseQualityScores(**payload)))
    if not scored:
        return

    summary = summarize_suite_quality(scored)
    result.quality_summary = summary.to_dict()

    print("\n=== Retrieval quality metrics ===")
    if summary.routing_accuracy is not None:
        print(f"routing_accuracy: {summary.routing_accuracy:.1%} ({summary.cases_scored} cases)")
    if summary.mean_entity_recall is not None:
        print(f"mean_entity_recall: {summary.mean_entity_recall:.2f}")
    if summary.mean_source_precision_at_k is not None:
        print(f"mean_source_precision@5: {summary.mean_source_precision_at_k:.2f}")
    if summary.mean_groundedness is not None:
        print(f"mean_groundedness: {summary.mean_groundedness:.2f}")
    if summary.mean_faithfulness is not None:
        print(f"mean_faithfulness: {summary.mean_faithfulness:.2f}")
    if summary.quality_failures:
        print(f"quality_gate_failures: {summary.quality_failures} (cases with explicit quality expect)")


def print_summary(result: SuiteResult) -> None:
    print("\n=== Chat regression summary ===")
    print(f"passed={result.passed} failed={result.failed} skipped={result.skipped}")
    for case in result.cases:
        status = "PASS" if case.passed else ("SKIP" if case.skipped else "FAIL")
        retrieval = f" retrieval={case.retrieval}" if case.retrieval else ""
        print(f"[{status}] {case.id} ({case.mode}{retrieval})")
        if not case.passed:
            print(f"       reason: {case.reason}")
            if case.answer_preview:
                print(f"       answer: {case.answer_preview}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ssi-chat regression suite")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument(
        "--eval-golden",
        action="store_true",
        help="Run labeled golden eval set (eval_golden.yaml) instead of full question bank",
    )
    parser.add_argument("--chat-url", default="http://localhost:8092")
    parser.add_argument("--harness-url", default="http://localhost:8091")
    parser.add_argument(
        "--instruction-service-url",
        dest="instruction_service_url",
        default="http://localhost:8000",
        help="instruction-service base URL (INSTRUCTION_SERVICE_URL)",
    )
    parser.add_argument("--payment-url", default="http://localhost:8093")
    parser.add_argument("--indexer-url", default="http://localhost:8090")
    parser.add_argument("--authz-url", default="http://localhost:8094")
    parser.add_argument("--mode", choices=["events", "instructions", "payments", "all"], default="all")
    parser.add_argument("--tags", default="", help="Comma-separated tag filter")
    parser.add_argument(
        "--retrieval",
        default="",
        help="Comma-separated retrieval filter: deterministic, graph, vector, eligibility",
    )
    parser.add_argument("--ids", default="", help="Comma-separated case id filter")
    parser.add_argument("--seed", action="store_true", help="Run harness seed steps before tests")
    parser.add_argument("--no-wait", action="store_true", help="Skip waiting for ETL index after seed")
    parser.add_argument(
        "--skip-api-smoke",
        action="store_true",
        help="Skip cross-service API smoke checks",
    )
    parser.add_argument(
        "--api-smoke-only",
        action="store_true",
        help="Run API smoke checks only (no chat cases)",
    )
    parser.add_argument("--report", type=Path, help="Write JSON report to this path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    suite = load_suite(DEFAULT_GOLDEN if args.eval_golden else args.questions)
    tag_filter = {tag.strip() for tag in args.tags.split(",") if tag.strip()} or None
    retrieval_filter = {item.strip() for item in args.retrieval.split(",") if item.strip()} or None
    id_filter = {item.strip() for item in args.ids.split(",") if item.strip()} or None
    cases = filter_cases(
        suite.cases,
        mode=args.mode,
        tags=tag_filter,
        case_ids=id_filter,
        retrieval=retrieval_filter,
    )

    if args.seed and suite.seed.steps:
        logger.info("running %s seed step(s)", len(suite.seed.steps))
        run_seed(args.harness_url, suite.seed)
        if not args.no_wait:
            wait_for_index(
                harness_url=args.harness_url,
                indexer_url=args.indexer_url,
                min_security_events=suite.seed.wait.min_security_events,
                min_multimodal_documents=suite.seed.wait.min_multimodal_documents,
                timeout_seconds=suite.seed.wait.timeout_seconds,
                poll_interval_seconds=suite.seed.wait.poll_interval_seconds,
            )

    context = fetch_context(
        harness_url=args.harness_url,
        instruction_service_url=args.instruction_service_url,
        payment_url=args.payment_url,
    )
    logger.info("resolved context keys: %s", sorted(context))

    started = time.perf_counter()
    smoke_result = None
    if not args.skip_api_smoke:
        smoke_result = run_api_smoke(
            harness_url=args.harness_url,
            instruction_service_url=args.instruction_service_url,
            payment_url=args.payment_url,
            indexer_url=args.indexer_url,
            chat_url=args.chat_url,
            authz_url=args.authz_url,
            context=context,
        )
        print_smoke_summary(smoke_result)

    result = SuiteResult(context=context)
    chat_failed = 0

    if not args.api_smoke_only:
        with httpx.Client() as client:
            health = client.get(f"{args.chat_url.rstrip('/')}/health", timeout=15.0)
            health.raise_for_status()
            auth_headers = compliance_auth_headers(client, args.chat_url)

            for index, case in enumerate(cases, start=1):
                logger.info("[%s/%s] %s", index, len(cases), case.id)
                case_result = run_case(
                    client, args.chat_url, case, context, auth_headers=auth_headers
                )
                result.cases.append(case_result)
                if case_result.skipped:
                    result.skipped += 1
                elif case_result.passed:
                    result.passed += 1
                else:
                    result.failed += 1
                    chat_failed += 1

        print_summary(result)
        print_quality_summary(result)
        print(f"\nCompleted {len(cases)} chat case(s)")

    elapsed = time.perf_counter() - started
    print(f"Total elapsed: {elapsed:.1f}s")

    if args.report:
        payload: dict = {"elapsed_seconds": round(elapsed, 2), "context": context}
        if smoke_result is not None:
            payload["api_smoke"] = smoke_to_dict(smoke_result)
        if not args.api_smoke_only:
            payload["chat"] = result.to_dict()
        args.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Report written to {args.report}")

    smoke_failed = smoke_result.failed if smoke_result is not None else 0
    return 1 if smoke_failed or chat_failed else 0


if __name__ == "__main__":
    sys.exit(main())
