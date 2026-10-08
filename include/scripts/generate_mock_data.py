import os
import pandas as pd
from datetime import datetime, timedelta

def generate_mock_data(output_dir="include/data"):
    """Generates mock input CSV files for sales, inventory snapshot, and supplier contracts."""
    os.makedirs(output_dir, exist_ok=True)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    sales = [
        ("TXN-1001", yesterday, "SKU-101", 10, 75.0), ("TXN-1002", yesterday, "SKU-101", 2, 75.0),
        ("TXN-1003", yesterday, "SKU-102", 14, 30.0), ("TXN-1004", yesterday, "SKU-103", 4, 350.0),
        ("TXN-1005", yesterday, "SKU-104", 18, 45.0), ("TXN-1006", yesterday, "SKU-105", 6, 180.0),
        ("TXN-1007", yesterday, "SKU-106", 9, 60.0)
    ]
    pd.DataFrame(sales, columns=["transaction_id", "date", "sku", "units_sold", "unit_price"]).to_csv(f"{output_dir}/sales_yesterday.csv", index=False)

    inventory = [
        ("SKU-101", "Ergonomic Mechanical Keyboard", 15, 20), ("SKU-102", "Ergonomic Wireless Mouse", 120, 30),
        ("SKU-103", "27-inch 4K UHD Monitor", 8, 10),         ("SKU-104", "Multi-Port USB-C Hub", 45, 25),
        ("SKU-105", "Noise Canceling Headphones", 200, 50),  ("SKU-106", "1080p HD Streaming Webcam", 10, 15)
    ]
    pd.DataFrame(inventory, columns=["sku", "product_name", "current_stock", "safety_stock"]).to_csv(f"{output_dir}/inventory_snapshot.csv", index=False)

    suppliers = [
        ("SUP-01", "LogiTech Logistics Inc", "SKU-101", 5, 50), ("SUP-01", "LogiTech Logistics Inc", "SKU-102", 3, 40),
        ("SUP-02", "Apex Display Solutions", "SKU-103", 7, 20), ("SUP-03", "ConnectX Peripherals", "SKU-104", 2, 50),
        ("SUP-02", "Apex Display Solutions", "SKU-105", 4, 30), ("SUP-03", "ConnectX Peripherals", "SKU-106", 3, 25)
    ]
    pd.DataFrame(suppliers, columns=["supplier_id", "supplier_name", "sku", "lead_time_days", "moq"]).to_csv(f"{output_dir}/suppliers_master.csv", index=False)

if __name__ == "__main__":
    generate_mock_data()
