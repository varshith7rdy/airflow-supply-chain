import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def validate_inputs(sales_df: pd.DataFrame, inventory_df: pd.DataFrame, suppliers_df: pd.DataFrame):
    """Validates data schemas, non-null status, and non-negative constraints."""
    schemas = {
        "sales": (sales_df, {"transaction_id", "date", "sku", "units_sold", "unit_price"}),
        "inventory": (inventory_df, {"sku", "product_name", "current_stock", "safety_stock"}),
        "suppliers": (suppliers_df, {"supplier_id", "supplier_name", "sku", "lead_time_days", "moq"}),
    }
    for name, (df, cols) in schemas.items():
        if not cols.issubset(df.columns) or df.isnull().any().any():
            raise ValueError(f"Validation failed for {name} dataset.")

    if (sales_df['units_sold'] < 0).any() or (inventory_df['current_stock'] < 0).any():
        raise ValueError("Invalid negative values found in sales/inventory.")
    return True

def calculate_mrp(sales_df: pd.DataFrame, inventory_df: pd.DataFrame, suppliers_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates ROP, MOQ-adjusted order quantity, and critical stockout risk."""
    burn_df = sales_df.groupby("sku", as_index=False).agg(
        daily_burn_rate=("units_sold", "sum"), unit_price=("unit_price", "mean")
    )
    mrp = inventory_df.merge(suppliers_df, on="sku").merge(burn_df, on="sku", how="left").fillna(0)
    mrp["reorder_point"] = (mrp["daily_burn_rate"] * mrp["lead_time_days"]) + mrp["safety_stock"]

    replenish = mrp[mrp["current_stock"] <= mrp["reorder_point"]].copy()
    if replenish.empty:
        return pd.DataFrame()

    raw_needed = (replenish["reorder_point"] + replenish["safety_stock"]) - replenish["current_stock"]
    multipliers = np.ceil(np.maximum(raw_needed, replenish["moq"]) / replenish["moq"])
    replenish["order_quantity"] = (multipliers * replenish["moq"]).astype(int)
    replenish["total_cost"] = replenish["order_quantity"] * replenish["unit_price"]
    replenish["critical_stockout_risk"] = replenish["current_stock"] < (replenish["daily_burn_rate"] * replenish["lead_time_days"])

    return replenish

def generate_vendor_po_files(replenish_df: pd.DataFrame, output_dir: str = "output/purchase_orders") -> list:
    """Generates vendor PO CSV files grouped by supplier_id."""
    os.makedirs(output_dir, exist_ok=True)
    if replenish_df.empty:
        return []

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    po_files = []

    for supp_id, group in replenish_df.groupby("supplier_id"):
        po_path = os.path.join(output_dir, f"po_supplier_{supp_id.lower().replace('-', '_')}.csv")
        po_df = pd.DataFrame({
            "po_number": f"PO-{supp_id}-{today.strftime('%Y%m%d')}",
            "supplier_id": group["supplier_id"],
            "supplier_name": group["supplier_name"],
            "order_date": today_str,
            "sku": group["sku"],
            "product_name": group["product_name"],
            "order_quantity": group["order_quantity"],
            "unit_price": group["unit_price"],
            "total_cost": group["total_cost"],
            "required_delivery_date": [(today + timedelta(days=int(lt))).strftime("%Y-%m-%d") for lt in group["lead_time_days"]],
            "critical_risk_flag": group["critical_stockout_risk"]
        })
        po_df.to_csv(po_path, index=False)
        po_files.append(po_path)

    return po_files

def generate_audit_log_and_webhook(replenish_df: pd.DataFrame, total_skus_analyzed: int, output_log_dir: str = "output/logs") -> dict:
    """Generates executive summary log and returns webhook notification dictionary."""
    os.makedirs(output_log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    reorder_skus = [] if replenish_df.empty else replenish_df["sku"].tolist()
    critical_skus = [] if replenish_df.empty else replenish_df[replenish_df["critical_stockout_risk"]]["sku"].tolist()
    total_pos = 0 if replenish_df.empty else replenish_df["supplier_id"].nunique()
    total_spend = 0.0 if replenish_df.empty else float(replenish_df["total_cost"].sum())

    summary = (
        f"="*60 + f"\n        PROCUREMENT AUDIT SUMMARY - {timestamp}\n" + "="*60 + "\n"
        f"Total SKUs Analyzed:        {total_skus_analyzed}\n"
        f"SKUs Requiring Reorder:     {len(reorder_skus)} ({', '.join(reorder_skus) if reorder_skus else 'None'})\n"
        f"Total POs Generated:        {total_pos}\n"
        f"Total Estimated Spend:      ${total_spend:,.2f}\n"
        f"Critical Stockout Risk SKUs: {len(critical_skus)} ({', '.join(critical_skus) if critical_skus else 'None'})\n"
        f"="*60 + "\n"
    )

    with open(os.path.join(output_log_dir, "procurement_summary.log"), "a") as f:
        f.write(summary + "\n")

    return {
        "event": "procurement_mrp_execution_complete",
        "timestamp": timestamp,
        "metrics": {
            "total_skus_analyzed": total_skus_analyzed,
            "reorder_skus_count": len(reorder_skus),
            "total_pos_generated": total_pos,
            "total_estimated_spend_usd": total_spend,
            "critical_stockout_risk_count": len(critical_skus),
        },
        "critical_skus": critical_skus,
        "status": "ACTION_REQUIRED" if critical_skus else "NORMAL"
    }
