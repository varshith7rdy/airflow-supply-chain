import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime, timedelta

try:
    from airflow.sdk import dag, task
except ImportError:
    from airflow.decorators import dag, task

# Ensure project root is in python path for local imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from include.scripts.generate_mock_data import generate_mock_data
from include.scripts.mrp_calculator import (
    validate_inputs,
    calculate_mrp,
    generate_vendor_po_files,
    generate_audit_log_and_webhook,
)

logger = logging.getLogger("airflow.task")

default_args = {
    "owner": "supply_chain_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

@dag(
    dag_id="supply_chain_mrp_pipeline",
    default_args=default_args,
    description="Automated Supply Chain MRP & Vendor PO Pipeline",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["supply_chain", "mrp", "inventory", "purchase_orders"],
)
def supply_chain_mrp_pipeline():

    @task()
    def ingest_daily_operations() -> dict:
        """
        Task 1: Ingest yesterday's sales, inventory snapshot, and supplier contracts.
        Ensures input files exist (generating mock data if missing) and validates schemas.
        """
        data_dir = os.path.join(PROJECT_ROOT, "include", "data")
        sales_file = os.path.join(data_dir, "sales_yesterday.csv")
        inv_file = os.path.join(data_dir, "inventory_snapshot.csv")
        supp_file = os.path.join(data_dir, "suppliers_master.csv")

        # Auto-generate mock input data if files are missing
        if not (os.path.exists(sales_file) and os.path.exists(inv_file) and os.path.exists(supp_file)):
            logger.info("Mock input files missing. Generating default mock data...")
            generate_mock_data(output_dir=data_dir)

        sales_df = pd.read_csv(sales_file)
        inv_df = pd.read_csv(inv_file)
        supp_df = pd.read_csv(supp_file)

        # Perform data validation
        validate_inputs(sales_df, inv_df, supp_df)

        logger.info(f"Ingested {len(sales_df)} sales records, {len(inv_df)} inventory records, {len(supp_df)} supplier contracts.")

        return {
            "sales": sales_df.to_dict(orient="records"),
            "inventory": inv_df.to_dict(orient="records"),
            "suppliers": supp_df.to_dict(orient="records"),
            "total_skus_analyzed": int(inv_df["sku"].nunique()),
        }

    @task()
    def calculate_net_requirements(ingested_data: dict) -> dict:
        """
        Task 2: Calculate Reorder Point (ROP), net replenishment requirements,
        MOQ rounding, and flag critical stockout risks.
        """
        sales_df = pd.DataFrame(ingested_data["sales"])
        inv_df = pd.DataFrame(ingested_data["inventory"])
        supp_df = pd.DataFrame(ingested_data["suppliers"])
        total_skus_analyzed = ingested_data["total_skus_analyzed"]

        replenish_df = calculate_mrp(sales_df, inv_df, supp_df)

        logger.info(f"Calculated net requirements. {len(replenish_df)} SKUs flagged for replenishment.")

        return {
            "replenishment_items": replenish_df.to_dict(orient="records") if not replenish_df.empty else [],
            "total_skus_analyzed": total_skus_analyzed,
        }

    @task()
    def generate_vendor_purchase_orders(mrp_results: dict) -> dict:
        """
        Task 3: Group flagged replenishment items by supplier_id and generate vendor PO CSV files.
        """
        items = mrp_results["replenishment_items"]
        total_skus_analyzed = mrp_results["total_skus_analyzed"]

        po_output_dir = os.path.join(PROJECT_ROOT, "output", "purchase_orders")
        replenish_df = pd.DataFrame(items) if items else pd.DataFrame()

        po_files = generate_vendor_po_files(replenish_df, output_dir=po_output_dir)

        logger.info(f"Generated {len(po_files)} Purchase Order files in {po_output_dir}")

        return {
            "replenishment_items": items,
            "total_skus_analyzed": total_skus_analyzed,
            "po_files": po_files,
        }

    @task()
    def audit_and_notify_procurement(po_results: dict):
        """
        Task 4: Compile executive procurement audit log and print formatted notification payload log.
        """
        items = po_results["replenishment_items"]
        total_skus_analyzed = po_results["total_skus_analyzed"]

        log_output_dir = os.path.join(PROJECT_ROOT, "output", "logs")
        replenish_df = pd.DataFrame(items) if items else pd.DataFrame()

        payload = generate_audit_log_and_webhook(
            replenish_df=replenish_df,
            total_skus_analyzed=total_skus_analyzed,
            output_log_dir=log_output_dir,
        )

        # Print formatted log mimicking notification webhook payload sent to procurement channel
        logger.info("\n" + "="*60)
        logger.info("[PROCUREMENT NOTIFICATION WEBHOOK PAYLOAD SENT]")
        logger.info(json.dumps(payload, indent=2))
        logger.info("="*60 + "\n")

    # Pipeline execution flow
    ops_data = ingest_daily_operations()
    mrp_res = calculate_net_requirements(ops_data)
    po_res = generate_vendor_purchase_orders(mrp_res)
    audit_and_notify_procurement(po_res)

# Instantiate the DAG
dag_instance = supply_chain_mrp_pipeline()
