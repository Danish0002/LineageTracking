"""
Command Line Interface to run the customer record ingestion and synchronization data pipeline.
"""
import argparse
import sys
from services.pipeline import ingest_customer_record


def main():
    parser = argparse.ArgumentParser(
        description="Ingest customer record into Snowflake and synchronize to ADLS and Databricks."
    )
    parser.add_argument(
        "--customer-id", "-c",
        required=True,
        help="Customer ID to ingest (e.g. CUST_004)"
    )
    parser.add_argument(
        "--project-id", "-p",
        required=True,
        help="Project ID to assign (e.g. PROJ_003)"
    )

    args = parser.parse_args()

    try:
        print("============================================================")
        print(f"Starting Data Pipeline Ingestion")
        print(f"Customer ID: {args.customer_id}")
        print(f"Project ID:  {args.project_id}")
        print("============================================================")

        status = ingest_customer_record(args.customer_id, args.project_id)

        print("\n--- Pipeline Steps Execution Logs ---")
        for log in status["logs"]:
            print(f"[*] {log}")

        print("\n--- Pipeline Ingestion Status Summary ---")
        print(f"[Snowflake]  : {status['snowflake']}")
        print(f"[ADLS]       : {status['adls']}")
        print(f"[Databricks] : {status['databricks']}")
        print("============================================================")

        # Check if any step failed
        failures = [k for k, v in status.items() if k in ["snowflake", "adls", "databricks"] and "Fail" in str(v)]
        if failures:
            print(f"Pipeline finished with failures in: {', '.join(failures)}")
            sys.exit(1)
        else:
            print("Pipeline completed successfully!")
            sys.exit(0)

    except Exception as e:
        print(f"\n[ERROR] Pipeline execution crashed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
