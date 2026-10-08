import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime

try:
    from airflow.sdk import dag, task
except ImportError:
    from airflow.decorators import dag, task

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from include.scripts.generate_mock_data import generate_mock_data
from include.scripts.mrp_calculator import (
    validate_inputs, calculate_mrp, generate_vendor_po_files, generate_audit_log_and_webhook
)

logger = logging.getLogger("airflow.task")

@dag(
    dag_id="supply_chain_mrp_pipeline",
    description="Automated Supply Chain MRP & Vendor PO Pipeline",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["supply_chain", "mrp", "inventory", "purchase_orders"],
)
def supply_chain_mrp_pipeline():

    @task()
    def ingest_daily_operations() -> dict:
        data_dir = os.path.join(PROJECT_ROOT, "include", "data")
        sales_file = os.path.join(data_dir, "sales_yesterday.csv")
        inv_file = os.path.join(data_dir, "inventory_snapshot.csv")
        supp_file = os.path.join(data_dir, "suppliers_master.csv")

        if not all(os.path.exists(f) for f in [sales_file, inv_file, supp_file]):
            generate_mock_data(output_dir=data_dir)

        sales_df, inv_df, supp_df = pd.read_csv(sales_file), pd.read_csv(inv_file), pd.read_csv(supp_file)
        validate_inputs(sales_df, inv_df, supp_df)

        return {
            "sales": sales_df.to_dict(orient="records"),
            "inventory": inv_df.to_dict(orient="records"),
            "suppliers": supp_df.to_dict(orient="records"),
            "total_skus_analyzed": int(inv_df["sku"].nunique()),
        }

    @task()
    def calculate_net_requirements(data: dict) -> dict:
        replenish_df = calculate_mrp(
            pd.DataFrame(data["sales"]), pd.DataFrame(data["inventory"]), pd.DataFrame(data["suppliers"])
        )
        return {
            "replenishment_items": replenish_df.to_dict(orient="records") if not replenish_df.empty else [],
            "total_skus_analyzed": data["total_skus_analyzed"],
        }

    @task()
    def generate_vendor_purchase_orders(mrp_results: dict) -> dict:
        items = mrp_results["replenishment_items"]
        po_dir = os.path.join(PROJECT_ROOT, "output", "purchase_orders")
        po_files = generate_vendor_po_files(pd.DataFrame(items) if items else pd.DataFrame(), output_dir=po_dir)

        return {
            "replenishment_items": items,
            "total_skus_analyzed": mrp_results["total_skus_analyzed"],
            "po_files": po_files,
        }

    @task()
    def audit_and_notify_procurement(po_results: dict):
        items = po_results["replenishment_items"]
        payload = generate_audit_log_and_webhook(
            replenish_df=pd.DataFrame(items) if items else pd.DataFrame(),
            total_skus_analyzed=po_results["total_skus_analyzed"],
            output_log_dir=os.path.join(PROJECT_ROOT, "output", "logs"),
        )
        logger.info("\n" + "="*60 + "\n[PROCUREMENT NOTIFICATION WEBHOOK PAYLOAD SENT]\n" + json.dumps(payload, indent=2) + "\n" + "="*60)

    audit_and_notify_procurement(generate_vendor_purchase_orders(calculate_net_requirements(ingest_daily_operations())))

dag_instance = supply_chain_mrp_pipeline()
