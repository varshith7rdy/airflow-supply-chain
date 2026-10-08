import os
import math
import json
import pandas as pd
from datetime import datetime, timedelta

def validate_inputs(sales_df: pd.DataFrame, inventory_df: pd.DataFrame, suppliers_df: pd.DataFrame):
    """
    Validates schemas and checks for missing values or corrupt data types.
    Raises ValueError if validation fails.
    """
    required_sales_cols = {"transaction_id", "date", "sku", "units_sold", "unit_price"}
    required_inv_cols = {"sku", "product_name", "current_stock", "safety_stock"}
    required_supp_cols = {"supplier_id", "supplier_name", "sku", "lead_time_days", "moq"}

    if not required_sales_cols.issubset(sales_df.columns):
        raise ValueError(f"sales_df missing required columns: {required_sales_cols - set(sales_df.columns)}")
    if not required_inv_cols.issubset(inventory_df.columns):
        raise ValueError(f"inventory_df missing required columns: {required_inv_cols - set(inventory_df.columns)}")
    if not required_supp_cols.issubset(suppliers_df.columns):
        raise ValueError(f"suppliers_df missing required columns: {required_supp_cols - set(suppliers_df.columns)}")

    # Check missing values
    for name, df in [("sales", sales_df), ("inventory", inventory_df), ("suppliers", suppliers_df)]:
        if df.isnull().any().any():
            raise ValueError(f"Null/missing values detected in {name} dataset.")

    # Data type validations
    if (sales_df['units_sold'] < 0).any() or (sales_df['unit_price'] <= 0).any():
        raise ValueError("Invalid negative/zero values in sales data.")
    if (inventory_df['current_stock'] < 0).any() or (inventory_df['safety_stock'] < 0).any():
        raise ValueError("Invalid negative values in inventory data.")
    if (suppliers_df['lead_time_days'] <= 0).any() or (suppliers_df['moq'] <= 0).any():
        raise ValueError("Invalid lead_time or moq in suppliers data.")

    print("Data validation successful: all datasets passed schema, null, and range checks.")
    return True

def calculate_mrp(sales_df: pd.DataFrame, inventory_df: pd.DataFrame, suppliers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes daily burn rate, Reorder Point (ROP), replenishment quantities matching MOQs,
    and identifies critical stockout risks.
    Formula: ROP = (Daily Burn Rate * Supplier Lead Time) + Safety Stock
    """
    # Compute daily burn rate per SKU from sales
    burn_df = sales_df.groupby("sku", as_index=False).agg(
        daily_burn_rate=("units_sold", "sum"),
        unit_price=("unit_price", "mean")
    )

    # Merge inventory, supplier, and burn rate info
    mrp_df = pd.merge(inventory_df, suppliers_df, on="sku", how="inner")
    mrp_df = pd.merge(mrp_df, burn_df, on="sku", how="left")
    mrp_df["daily_burn_rate"] = mrp_df["daily_burn_rate"].fillna(0)
    mrp_df["unit_price"] = mrp_df["unit_price"].fillna(0)

    # Calculate Reorder Point (ROP)
    mrp_df["reorder_point"] = (mrp_df["daily_burn_rate"] * mrp_df["lead_time_days"]) + mrp_df["safety_stock"]

    # Filter items needing reorder (current_stock <= ROP)
    reorder_mask = mrp_df["current_stock"] <= mrp_df["reorder_point"]
    replenish_df = mrp_df[reorder_mask].copy()

    if replenish_df.empty:
        print("No items require replenishment today.")
        return pd.DataFrame()

    # Calculate required order quantity adjusted for MOQ
    # Target stock level = ROP + safety_stock
    def compute_moq_rounded_order(row):
        target_buffer = row["reorder_point"] + row["safety_stock"]
        raw_needed = target_buffer - row["current_stock"]
        moq = row["moq"]
        if raw_needed <= 0:
            return moq
        # Round up raw_needed to nearest multiple of MOQ
        multiplier = math.ceil(raw_needed / moq)
        return multiplier * moq

    replenish_df["order_quantity"] = replenish_df.apply(compute_moq_rounded_order, axis=1)
    replenish_df["total_cost"] = replenish_df["order_quantity"] * replenish_df["unit_price"]

    # Flag Critical Stockout Risk: current stock is less than consumption during lead time
    # (i.e. stock will hit 0 before supplier lead time elapses)
    replenish_df["critical_stockout_risk"] = replenish_df["current_stock"] < (replenish_df["daily_burn_rate"] * replenish_df["lead_time_days"])

    return replenish_df

def generate_vendor_po_files(replenish_df: pd.DataFrame, output_dir: str = "output/purchase_orders") -> list:
    """
    Groups replenishment items by supplier_id and writes vendor PO files.
    Returns list of generated file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    if replenish_df.empty:
        print("No purchase orders to generate.")
        return generated_files

    today = datetime.now()

    for supplier_id, group in replenish_df.groupby("supplier_id"):
        supplier_name = group["supplier_name"].iloc[0]
        po_filename = f"po_supplier_{supplier_id.lower().replace('-', '_')}.csv"
        po_path = os.path.join(output_dir, po_filename)

        po_records = []
        for idx, row in group.iterrows():
            delivery_date = (today + timedelta(days=int(row["lead_time_days"]))).strftime("%Y-%m-%d")
            po_records.append({
                "po_number": f"PO-{supplier_id}-{today.strftime('%Y%m%d')}",
                "supplier_id": row["supplier_id"],
                "supplier_name": row["supplier_name"],
                "order_date": today.strftime("%Y-%m-%d"),
                "sku": row["sku"],
                "product_name": row["product_name"],
                "order_quantity": row["order_quantity"],
                "unit_price": row["unit_price"],
                "total_cost": row["total_cost"],
                "required_delivery_date": delivery_date,
                "critical_risk_flag": row["critical_stockout_risk"]
            })

        po_df = pd.DataFrame(po_records)
        po_df.to_csv(po_path, index=False)
        generated_files.append(po_path)
        print(f"Generated PO for supplier {supplier_id} ({supplier_name}) at {po_path}")

    return generated_files

def generate_audit_log_and_webhook(replenish_df: pd.DataFrame, total_skus_analyzed: int, output_log_dir: str = "output/logs") -> dict:
    """
    Compiles executive procurement summary log and generates webhook payload dictionary.
    """
    os.makedirs(output_log_dir, exist_ok=True)
    log_file_path = os.path.join(output_log_dir, "procurement_summary.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if replenish_df.empty:
        total_pos = 0
        total_spend = 0.0
        critical_skus = []
        reorder_skus = []
    else:
        total_pos = replenish_df["supplier_id"].nunique()
        total_spend = float(replenish_df["total_cost"].sum())
        critical_skus = replenish_df[replenish_df["critical_stockout_risk"]]["sku"].tolist()
        reorder_skus = replenish_df["sku"].tolist()

    summary_lines = [
        "============================================================",
        f"        PROCUREMENT AUDIT SUMMARY - {timestamp}",
        "============================================================",
        f"Total SKUs Analyzed:        {total_skus_analyzed}",
        f"SKUs Requiring Reorder:     {len(reorder_skus)} ({', '.join(reorder_skus) if reorder_skus else 'None'})",
        f"Total POs Generated:        {total_pos}",
        f"Total Estimated Spend:      ${total_spend:,.2f}",
        f"Critical Stockout Risk SKUs: {len(critical_skus)} ({', '.join(critical_skus) if critical_skus else 'None'})",
        "============================================================",
    ]
    summary_text = "\n".join(summary_lines)

    with open(log_file_path, "a") as f:
        f.write(summary_text + "\n\n")

    print(f"Audit log written to {log_file_path}")

    # Webhook Notification Payload Mock
    webhook_payload = {
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

    return webhook_payload
