import os
import pandas as pd
from datetime import datetime, timedelta

def generate_mock_data(output_dir="include/data"):
    """Generates simple mock input CSV files for sales, inventory, and suppliers."""
    os.makedirs(output_dir, exist_ok=True)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. Sales Yesterday Data
    sales_df = pd.DataFrame([
        {"transaction_id": "TXN-1001", "date": yesterday, "sku": "SKU-101", "units_sold": 10, "unit_price": 75.0},
        {"transaction_id": "TXN-1002", "date": yesterday, "sku": "SKU-101", "units_sold": 2,  "unit_price": 75.0},
        {"transaction_id": "TXN-1003", "date": yesterday, "sku": "SKU-102", "units_sold": 14, "unit_price": 30.0},
        {"transaction_id": "TXN-1004", "date": yesterday, "sku": "SKU-103", "units_sold": 4,  "unit_price": 350.0},
        {"transaction_id": "TXN-1005", "date": yesterday, "sku": "SKU-104", "units_sold": 18, "unit_price": 45.0},
        {"transaction_id": "TXN-1006", "date": yesterday, "sku": "SKU-105", "units_sold": 6,  "unit_price": 180.0},
        {"transaction_id": "TXN-1007", "date": yesterday, "sku": "SKU-106", "units_sold": 9,  "unit_price": 60.0},
    ])
    sales_df.to_csv(os.path.join(output_dir, "sales_yesterday.csv"), index=False)

    # 2. Inventory Snapshot Data
    inventory_df = pd.DataFrame([
        {"sku": "SKU-101", "product_name": "Ergonomic Mechanical Keyboard", "current_stock": 15,  "safety_stock": 20},
        {"sku": "SKU-102", "product_name": "Ergonomic Wireless Mouse",       "current_stock": 120, "safety_stock": 30},
        {"sku": "SKU-103", "product_name": "27-inch 4K UHD Monitor",         "current_stock": 8,   "safety_stock": 10},
        {"sku": "SKU-104", "product_name": "Multi-Port USB-C Hub",           "current_stock": 45,  "safety_stock": 25},
        {"sku": "SKU-105", "product_name": "Noise Canceling Headphones",     "current_stock": 200, "safety_stock": 50},
        {"sku": "SKU-106", "product_name": "1080p HD Streaming Webcam",      "current_stock": 10,  "safety_stock": 15},
    ])
    inventory_df.to_csv(os.path.join(output_dir, "inventory_snapshot.csv"), index=False)

    # 3. Suppliers Master Data
    suppliers_df = pd.DataFrame([
        {"supplier_id": "SUP-01", "supplier_name": "LogiTech Logistics Inc",  "sku": "SKU-101", "lead_time_days": 5, "moq": 50},
        {"supplier_id": "SUP-01", "supplier_name": "LogiTech Logistics Inc",  "sku": "SKU-102", "lead_time_days": 3, "moq": 40},
        {"supplier_id": "SUP-02", "supplier_name": "Apex Display Solutions", "sku": "SKU-103", "lead_time_days": 7, "moq": 20},
        {"supplier_id": "SUP-03", "supplier_name": "ConnectX Peripherals",    "sku": "SKU-104", "lead_time_days": 2, "moq": 50},
        {"supplier_id": "SUP-02", "supplier_name": "Apex Display Solutions", "sku": "SKU-105", "lead_time_days": 4, "moq": 30},
        {"supplier_id": "SUP-03", "supplier_name": "ConnectX Peripherals",    "sku": "SKU-106", "lead_time_days": 3, "moq": 25},
    ])
    suppliers_df.to_csv(os.path.join(output_dir, "suppliers_master.csv"), index=False)

if __name__ == "__main__":
    generate_mock_data()
