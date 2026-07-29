#!/usr/bin/env python3
import argparse

import boto3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete every object version and delete marker in one bucket."
    )
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--confirm-bucket", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile")
    args = parser.parse_args()

    if (
        not args.bucket.strip()
        or args.bucket != args.confirm_bucket
    ):
        parser.error(
            "--confirm-bucket must exactly match the non-empty --bucket"
        )

    session_options = {"region_name": args.region}
    if args.profile:
        session_options["profile_name"] = args.profile

    client = boto3.Session(**session_options).client("s3")
    deleted_count = 0

    while True:
        response = client.list_object_versions(
            Bucket=args.bucket,
            MaxKeys=1000,
        )
        objects = [
            {
                "Key": item["Key"],
                "VersionId": item["VersionId"],
            }
            for item in (
                response.get("Versions", [])
                + response.get("DeleteMarkers", [])
            )
        ]

        if not objects:
            break

        delete_response = client.delete_objects(
            Bucket=args.bucket,
            Delete={
                "Objects": objects,
                "Quiet": True,
            },
        )

        if delete_response.get("Errors"):
            raise RuntimeError(
                "S3 did not delete every requested object version"
            )

        deleted_count += len(objects)

    print(
        f"Removed {deleted_count} object versions from {args.bucket}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
