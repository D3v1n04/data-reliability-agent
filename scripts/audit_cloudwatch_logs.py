#!/usr/bin/env python3
import argparse
import re
import sys
import time

import boto3


FORBIDDEN_PATTERNS = {
    "database URL": re.compile(r"(?i)(?:postgresql|cockroachdb)://"),
    "diagnosis evidence field": re.compile(
        r'(?i)"(?:embedding_input|incident_snapshot|error_message|'
        r'likely_causes|recommendations|explanation)"'
    ),
    "raw prompt text": re.compile(
        r"(?i)deterministic reliability engine is the source of truth"
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check recent backend logs for forbidden sensitive data."
    )
    parser.add_argument("--log-group", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile")
    parser.add_argument("--minutes", type=int, default=30)
    args = parser.parse_args()

    session_options = {"region_name": args.region}
    if args.profile:
        session_options["profile_name"] = args.profile

    client = boto3.Session(**session_options).client("logs")
    start_time = int(
        (time.time() - max(args.minutes, 1) * 60) * 1000
    )
    paginator = client.get_paginator("filter_log_events")
    violations: dict[str, int] = {
        name: 0 for name in FORBIDDEN_PATTERNS
    }

    for page in paginator.paginate(
        logGroupName=args.log_group,
        startTime=start_time,
    ):
        for event in page.get("events", []):
            message = event.get("message", "")
            for name, pattern in FORBIDDEN_PATTERNS.items():
                if pattern.search(message):
                    violations[name] += 1

    detected = {
        name: count
        for name, count in violations.items()
        if count
    }

    if detected:
        print(
            f"Sensitive log audit failed: {detected}",
            file=sys.stderr,
        )
        return 1

    print(
        "Sensitive log audit passed: no database URLs, diagnosis "
        "evidence fields, or raw prompt text were found."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
