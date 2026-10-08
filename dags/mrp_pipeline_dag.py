import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime

# Import Airflow TaskFlow decorators
try:
    from airflow.sdk import dag, task
except ImportError:
    from airflow.decorators import dag, task

# Set project root path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import our helper functions
from include.scripts.generate_mock_data import generate_mock_data
from include.scripts.mrp_calculator import (
    validate_inputs,
    calculate_mrp,
    generate_vendor_po_files,
    generate_audit_log_and_webhook,
)

logger = logging.getLogger("airflow.task")


@dag(
    dag_id="supply_chain_mrp_pipeline",
    description="Automated Supply Chain MRP & Vendor PO Pipeline",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["supply_chain", "mrp", "inventory"],
)
def supply_chain_mrp_pipeline():

    @task()
    def ingest_daily_operations() -> dict:
        """Task 1: Load and validate daily sales, inventory, and supplier data."""
        data_dir = os.path.join(PROJECT_ROOT, "include", "data")
        sales_path = os.path.join(data_dir, "sales_yesterday.csv")
        inv_path = os.path.join(data_dir, "inventory_snapshot.csv")
        supp_path = os.path.join(data_dir, "suppliers_master.csv")

        # Create mock data if files are missing
        if not (os.path.exists(sales_path) and os.path.exists(inv_path) and os.path.exists(supp_path)):
            generate_mock_data(output_dir=data_dir)

        # Read CSVs into DataFrames
        sales_df = pd.read_csv(sales_path)
        inv_df = pd.read_csv(inv_path)
        supp_df = pd.read_csv(supp_path)

        validate_inputs(sales_df, inv_df, supp_df)

        return {
            "sales": sales_df.to_dict(orient="records"),
            "inventory": inv_df.to_dict(orient="records"),
            "suppliers": supp_df.to_dict(orient="records"),
            "total_skus": int(inv_df["sku"].nunique()),
        }

    @task()
    def calculate_net_requirements(operations_data: dict) -> dict:
        """Task 2: Calculate Reorder Point (ROP), MOQ quantities, and stockout risks."""
        sales_df = pd.DataFrame(operations_data["sales"])
        inv_df = pd.DataFrame(operations_data["inventory"])
        supp_df = pd.DataFrame(operations_data["suppliers"])

        # Compute MRP replenishment items
        replenish_df = calculate_mrp(sales_df, inv_df, supp_df)

        return {
            "reorder_items": replenish_df.to_dict(orient="records") if not replenish_df.empty else [],
            "total_skus": operations_data["total_skus"],
        }

    @task()
    def generate_vendor_purchase_orders(mrp_results: dict) -> dict:
        """Task 3: Group items by supplier and write Purchase Order CSV files."""
        items = mrp_results["reorder_items"]
        replenish_df = pd.DataFrame(items) if items else pd.DataFrame()
        po_dir = os.path.join(PROJECT_ROOT, "output", "purchase_orders")

        po_files = generate_vendor_po_files(replenish_df, output_dir=po_dir)

        return {
            "reorder_items": items,
            "total_skus": mrp_results["total_skus"],
            "po_files": po_files,
        }

    @task()
    def audit_and_notify_procurement(po_results: dict):
        """Task 4: Write procurement audit log and output notification alert."""
        items = po_results["reorder_items"]
        replenish_df = pd.DataFrame(items) if items else pd.DataFrame()
        log_dir = os.path.join(PROJECT_ROOT, "output", "logs")

        payload = generate_audit_log_and_webhook(replenish_df, po_results["total_skus"], output_log_dir=log_dir)

        # Print formatted log for procurement channel
        logger.info("\n" + "=" * 60 + "\n[NOTIFICATION WEBHOOK SENT TO PROCUREMENT CHANNEL]\n" + json.dumps(payload, indent=2) + "\n" + "=" * 60)

    # Define task dependencies sequentially
    data = ingest_daily_operations()
    mrp = calculate_net_requirements(data)
    pos = generate_vendor_purchase_orders(mrp)
    audit_and_notify_procurement(pos)


# Instantiate the Airflow DAG
dag_instance = supply_chain_mrp_pipeline()
