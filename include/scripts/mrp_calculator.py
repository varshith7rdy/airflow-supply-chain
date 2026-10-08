import os
import math
import json
import pandas as pd
from datetime import datetime, timedelta

def validate_inputs(sales_df: pd.DataFrame, inventory_df: pd.DataFrame, suppliers_df: pd.DataFrame):
    """Simple check to make sure input datasets are not empty and contain data."""
    if sales_df.empty or inventory_df.empty or suppliers_df.empty:
        raise ValueError("One or more input files are empty!")
    return True

def calculate_mrp(sales_df: pd.DataFrame, inventory_df: pd.DataFrame, suppliers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Core MRP Logic:
    1. Compute daily burn rate per SKU from sales history.
    2. Compute Reorder Point (ROP) = (Burn Rate * Lead Time) + Safety Stock.
    3. Determine order quantity rounded up to supplier MOQ.
    4. Flag critical stockout risks (stock running out before delivery).
    """
    # 1. Calculate daily burn rate (total units sold per SKU)
    burn_rates = sales_df.groupby("sku", as_index=False).agg(
        daily_burn_rate=("units_sold", "sum"),
        unit_price=("unit_price", "mean")
    )

    # 2. Combine inventory, supplier details, and sales burn rates
    mrp_df = inventory_df.merge(suppliers_df, on="sku").merge(burn_rates, on="sku", how="left").fillna(0)

    # 3. Calculate Reorder Point (ROP) for every item
    mrp_df["reorder_point"] = (mrp_df["daily_burn_rate"] * mrp_df["lead_time_days"]) + mrp_df["safety_stock"]

    # 4. Filter only items that need reordering (current_stock <= Reorder Point)
    reorder_items = mrp_df[mrp_df["current_stock"] <= mrp_df["reorder_point"]].copy()
    if reorder_items.empty:
        return pd.DataFrame()

    # 5. Calculate Order Quantity rounded up to Supplier MOQ
    order_quantities = []
    total_costs = []
    critical_risks = []

    for _, row in reorder_items.iterrows():
        # Target stock level buffer
        target_buffer = row["reorder_point"] + row["safety_stock"]
        raw_needed = target_buffer - row["current_stock"]
        moq = row["moq"]

        # Round up to nearest multiple of MOQ
        needed = max(raw_needed, moq)
        final_order_qty = math.ceil(needed / moq) * moq

        # Critical risk: current stock is less than expected usage during lead time
        is_critical = row["current_stock"] < (row["daily_burn_rate"] * row["lead_time_days"])

        order_quantities.append(final_order_qty)
        total_costs.append(final_order_qty * row["unit_price"])
        critical_risks.append(is_critical)

    reorder_items["order_quantity"] = order_quantities
    reorder_items["total_cost"] = total_costs
    reorder_items["critical_stockout_risk"] = critical_risks

    return reorder_items

def generate_vendor_po_files(replenish_df: pd.DataFrame, output_dir: str = "output/purchase_orders") -> list:
    """Group replenishment items by supplier and create simple Purchase Order CSV files."""
    os.makedirs(output_dir, exist_ok=True)
    if replenish_df.empty:
        return []

    today = datetime.now()
    po_files = []

    for supplier_id, group in replenish_df.groupby("supplier_id"):
        po_file_path = os.path.join(output_dir, f"po_supplier_{supplier_id.lower().replace('-', '_')}.csv")
        
        # Build PO table
        po_table = pd.DataFrame({
            "po_number": f"PO-{supplier_id}-{today.strftime('%Y%m%d')}",
            "supplier_id": group["supplier_id"],
            "supplier_name": group["supplier_name"],
            "order_date": today.strftime("%Y-%m-%d"),
            "sku": group["sku"],
            "product_name": group["product_name"],
            "order_quantity": group["order_quantity"],
            "unit_price": group["unit_price"],
            "total_cost": group["total_cost"],
            "delivery_date": [(today + timedelta(days=int(lt))).strftime("%Y-%m-%d") for lt in group["lead_time_days"]],
            "critical_risk": group["critical_stockout_risk"]
        })
        
        po_table.to_csv(po_file_path, index=False)
        po_files.append(po_file_path)

    return po_files

def generate_audit_log_and_webhook(replenish_df: pd.DataFrame, total_skus: int, output_log_dir: str = "output/logs") -> dict:
    """Write audit log file and prepare summary report payload for management."""
    os.makedirs(output_log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    reorder_skus = replenish_df["sku"].tolist() if not replenish_df.empty else []
    critical_skus = replenish_df[replenish_df["critical_stockout_risk"]]["sku"].tolist() if not replenish_df.empty else []
    total_pos = replenish_df["supplier_id"].nunique() if not replenish_df.empty else 0
    total_spend = float(replenish_df["total_cost"].sum()) if not replenish_df.empty else 0.0

    # Human-readable executive summary log
    log_content = (
        f"============================================================\n"
        f"        PROCUREMENT AUDIT SUMMARY - {timestamp}\n"
        f"============================================================\n"
        f"Total SKUs Analyzed:        {total_skus}\n"
        f"SKUs Requiring Reorder:     {len(reorder_skus)} ({', '.join(reorder_skus) if reorder_skus else 'None'})\n"
        f"Total POs Generated:        {total_pos}\n"
        f"Total Estimated Spend:      ${total_spend:,.2f}\n"
        f"Critical Stockout Risk SKUs: {len(critical_skus)} ({', '.join(critical_skus) if critical_skus else 'None'})\n"
        f"============================================================\n"
    )

    with open(os.path.join(output_log_dir, "procurement_summary.log"), "a") as f:
        f.write(log_content + "\n")

    return {
        "event": "procurement_mrp_complete",
        "timestamp": timestamp,
        "metrics": {
            "total_skus_analyzed": total_skus,
            "reorder_count": len(reorder_skus),
            "total_pos": total_pos,
            "total_spend_usd": total_spend,
            "critical_risk_count": len(critical_skus),
        },
        "critical_skus": critical_skus,
        "status": "ALERT" if critical_skus else "OK"
    }
