# 📦 Beginner's Guide: Supply Chain Terms & Pipeline Workflow

This guide breaks down all the supply chain jargon and concepts used in the Airflow pipeline into everyday human terms with simple real-world analogies.

---

## 🔑 Key Supply Chain Terms Explained

### 1. SKU (Stock Keeping Unit)
- **What it means**: A unique product barcode or identification code.
- **Analogy**: Like a social security number or passport number for a specific product.
- **Example**: `SKU-101` = *Ergonomic Mechanical Keyboard*. If you sell black keyboards vs white keyboards, each variant gets its own SKU code.

### 2. Daily Burn Rate
- **What it means**: How fast customers are buying an item per day.
- **Analogy**: How fast your car's fuel tank empties while driving.
- **Example**: If customers bought 12 keyboards yesterday, your daily burn rate is 12 units/day.

### 3. Lead Time (Days)
- **What it means**: How long a supplier takes to deliver an order after you place it.
- **Analogy**: Ordering food on DoorDash. If you place an order at 6:00 PM and it arrives at 6:30 PM, your lead time is 30 minutes.
- **Example**: Lead time = 5 days. If you order from *LogiTech Logistics* on Monday, the box arrives at your warehouse on Saturday.

### 4. Safety Stock
- **What it means**: Emergency buffer stock kept in the warehouse just in case sales suddenly surge or supplier shipping gets delayed.
- **Analogy**: The spare tire in your car trunk.
- **Example**: Safety stock = 20 units. Even if regular stock reaches 0, you still have 20 emergency units so customers aren't disappointed.

### 5. Reorder Point (ROP)
- **What it means**: The threshold stock level that triggers a "time to reorder" warning.
- **Analogy**: The low-fuel warning light on your car dashboard.
- **Formula**:
  $$\text{Reorder Point} = (\text{Daily Sales Burn Rate} \times \text{Supplier Lead Time}) + \text{Safety Stock}$$
- **Real Example**:
  - Customers buy 10 keyboards/day.
  - Delivery takes 5 days (you will sell $10 \times 5 = 50$ keyboards while waiting for delivery).
  - You want 20 emergency safety keyboards.
  - $\text{ROP} = 50 + 20 = 70 \text{ keyboards}$.
  - **Result**: As soon as warehouse stock drops to 70 keyboards, the system automatically triggers a reorder!

### 6. MOQ (Minimum Order Quantity)
- **What it means**: The smallest batch size a supplier is willing to sell to you in one order.
- **Analogy**: Buying eggs at the grocery store. You can't buy 3 loose eggs; you must buy a full carton of 12 eggs.
- **Example**: You need 15 keyboards, but the supplier's MOQ is 50. You MUST order at least 50 (or 100, 150), rounding UP to the nearest 50.

### 7. Replenishment Items
- **What it means**: The list of products that dropped below their Reorder Point today and officially need to be restocked.

### 8. Critical Stockout Risk
- **What it means**: An urgent alert when stock is dangerously low and will hit ZERO *before* the supplier delivery can even arrive.
- **Analogy**: Your gas light turned on, but you are 60 miles away from the nearest gas station and only have 20 miles of fuel left. You are going to get stranded!
- **Example**: You only have 15 keyboards left in the warehouse. Delivery takes 5 days, and customers buy 10/day (you need 50 during waiting time). Since $15 < 50$, you will hit zero stock in 1.5 days!

### 9. Purchase Order (PO) & PO Table
- **What it means**: The official invoice/order contract sent to a supplier.
- **Analogy**: An official receipt/order form.
- **Example**: A CSV file listing: *"Order PO-SUP-01: Buy 50 Keyboards at $75/unit ($3,750 total). Required delivery date: Oct 13, 2026."*

---

## 🔄 End-to-End Workflow (How Data Flows Step-by-Step)

```text
[Step 1: Ingest Data]  --> [Step 2: Calculate MRP] --> [Step 3: Generate POs] --> [Step 4: Audit & Alert]
Reads Sales, Inventory,    Computes ROP & MOQs     Creates Vendor PO CSVs      Logs summary & sends
& Supplier CSVs            Flags items to reorder  grouped by Supplier ID      Slack/Webhook alert
```

1. **Step 1 (`ingest_daily_operations`)**: Airflow reads 3 CSV files (yesterday's sales, current stock level, supplier contracts) and checks for errors.
2. **Step 2 (`calculate_net_requirements`)**: The system calculates daily burn rates, compares current stock against the Reorder Point (ROP), rounds needed quantities up to supplier MOQs, and flags any Critical Stockout Risks.
3. **Step 3 (`generate_vendor_purchase_orders`)**: Flags items by supplier and automatically creates separate Purchase Order CSV files (e.g. `po_supplier_sup_01.csv`).
4. **Step 4 (`audit_and_notify_procurement`)**: Compiles an executive summary report detailing total spend and flags urgent critical stockout risks for the management team.
