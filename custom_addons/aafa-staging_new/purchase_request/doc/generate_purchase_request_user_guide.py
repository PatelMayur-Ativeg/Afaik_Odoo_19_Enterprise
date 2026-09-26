#!/usr/bin/env python3
"""
Generate Purchase Request module user guide PDF.
Run: python generate_purchase_request_user_guide.py
Requires: pip install fpdf2
"""
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    raise SystemExit("Install fpdf2: pip install fpdf2")

OUT = Path(__file__).resolve().parent / "Purchase_Request_User_Guide.pdf"


class Guide(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(16, 16, 16)

    def cw(self):
        return self.w - self.l_margin - self.r_margin

    def cover(self):
        self.add_page()
        self.set_fill_color(25, 65, 115)
        self.rect(0, 0, self.w, 48, "F")
        self.set_y(14)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(255, 255, 255)
        self.cell(self.w, 10, "Purchase Request Module", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 12)
        self.cell(self.w, 7, "User Guide & Step-by-Step Examples", align="C")
        self.ln(38)
        self.set_text_color(50, 50, 50)
        self.set_font("Helvetica", "", 11)
        self.multi_cell(
            self.w,
            6,
            "This document explains what the module does, how the approval "
            "flow works, and how to use it with practical examples.",
            align="C",
        )

    def part(self, num, title):
        self.add_page()
        self.set_fill_color(25, 65, 115)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 255, 255)
        self.cell(self.cw(), 10, f"  Part {num}: {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def sec(self, title):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(25, 65, 115)
        self.multi_cell(self.cw(), 7, title)
        self.ln(1)
        self.set_text_color(0, 0, 0)

    def p(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(self.cw(), 5.5, text)
        self.ln(1)

    def li(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(self.cw(), 5.5, "   -  " + text)

    def step(self, n, text):
        self.set_font("Helvetica", "B", 10)
        self.cell(9, 5.5, f"{n}.")
        self.set_font("Helvetica", "", 10)
        self.multi_cell(self.cw() - 9, 5.5, text)

    def example_box(self, title, steps):
        self.ln(2)
        self.set_fill_color(248, 251, 255)
        self.set_draw_color(25, 65, 115)
        y0 = self.get_y()
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(25, 65, 115)
        self.cell(self.cw(), 7, f"  {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 10)
        for i, s in enumerate(steps, 1):
            self.multi_cell(self.cw() - 4, 5.5, f"   {i}. {s}")
        y1 = self.get_y() + 2
        self.rect(self.l_margin, y0, self.cw(), y1 - y0, "D")
        self.set_y(y1)


def build():
    g = Guide()
    g.set_auto_page_break(auto=True, margin=16)
    g.cover()

    # ===== PART 1: FUNCTIONALITY =====
    g.part(1, "Module Functionality")

    g.sec("1.1 Purpose")
    g.p(
        "The Purchase Request module is the starting point for internal purchasing. "
        "Employees describe what they need; managers approve; then the company either "
        "buys from a supplier (Purchase Order) or moves stock internally (Internal Picking). "
        "Everything is tracked on one form with a reference number (e.g. PR00015)."
    )

    g.sec("1.2 Main features")
    g.li("Create purchase requests with automatic reference number (PR#####).")
    g.li("Two product categories: General and IT (filters available products).")
    g.li("Three ways to fulfill each line: buy, take from stock, or both (partial).")
    g.li("Request items not in the catalog (New Product Request).")
    g.li("Approval workflow with email to the department manager.")
    g.li("Budget check for managers (planned, actual, remaining).")
    g.li("Link to Purchase Orders and Stock Transfers from the request.")
    g.li("Discussion and history on each request (messages at the bottom).")

    g.sec("1.3 Who uses the module")
    g.li("Employee (Requester) - Creates and submits requests.")
    g.li("Manager (Requisition Responsible) - Reviews, approves, or rejects.")
    g.li("PR Admin / PR IT Admin - Creates RFQ for new products; may edit cost price.")
    g.li("Procurement - Works on linked Purchase Orders in the Purchase app.")
    g.li("Warehouse - Validates internal transfers linked to the request.")

    g.sec("1.4 Where to open it")
    g.li("App menu: Purchase Requests")
    g.li("Or: Purchase > Orders > Purchase Requests")

    g.sec("1.5 Approval flow (status bar)")
    g.p(
        "Draft  ->  Waiting for Review  ->  Waiting for Approval  ->  "
        "In Progress  ->  Done"
    )
    g.p("Rejected stops the process. The requester is notified by email when submitted.")

    g.sec("1.6 Form sections")
    g.li("Header - Buttons: Submit, Approve, Reject, Done, Create RFQ (special cases).")
    g.li("Main fields - Employee, department, manager, category, dates, budget (if visible).")
    g.li("Products tab - Standard catalog lines.")
    g.li("New Products Request tab - When New Product Request is enabled.")
    g.li("Picking Details - Warehouse operation and locations.")
    g.li("Smart buttons - Purchase Orders count, Pickings count (warehouse managers).")

    g.sec("1.7 Line options (Requisition Action)")
    g.li("Internal Picking - Move stock between locations (no supplier).")
    g.li("Purchase Order - Create purchase from vendor (supplier required on product).")
    g.li("Partial - Use available stock first; buy the remaining quantity.")
    g.p(
        "Available QTY on each line shows stock in locations marked for PR. "
        "Qty to Buy and Qty to Receive are calculated for partial lines."
    )

    g.sec("1.8 Budget fields (when visible)")
    g.p(
        "Visible to department managers and users with budget access. Shows whether "
        "the department has enough budget before approval. Remaining budget turns "
        "red if the request may exceed the limit."
    )

    # ===== PART 2: HOW TO USE =====
    g.part(2, "How to Use (By Role)")

    g.sec("2.1 Employee - Create a request")
    g.step(1, "Open Purchase Requests and click New.")
    g.step(2, "Confirm Employee and Department (filled from your HR profile).")
    g.step(3, "Select Category: General or IT.")
    g.step(4, "Optional: PR Type, Budget Type, description, dates.")
    g.step(5, "Products tab: add lines (product, qty, action, vendors if buying).")
    g.step(6, "Check Picking Details if using internal stock.")
    g.step(7, "Click Submit for Approval.")
    g.p("You can only use Submit if you created the request.")

    g.sec("2.2 Manager - Review and decide")
    g.step(1, "Open requests in Waiting for Review or Waiting for Approval.")
    g.step(2, "Review lines, budget, and picking details.")
    g.step(3, "Optional: click Request approval to move to Waiting for Approval.")
    g.step(4, "Click Approve to accept, or Reject to decline.")
    g.step(5, "When work is finished, click Done.")
    g.step(6, "Use Reset to Draft to send back for correction if needed.")

    g.sec("2.3 Procurement - New products and purchase orders")
    g.step(1, "For catalog items: after approval, process via Purchase Orders linked to the PR.")
    g.step(2, "Click the Purchase Orders smart button on the request.")
    g.step(3, "For new products: open PR with only New Product lines, status Waiting for Review.")
    g.step(4, "Click Create RFQ, select vendor, confirm.")
    g.step(5, "Complete RFQ/PO in Purchase app as usual.")

    g.sec("2.4 Warehouse - Internal transfers")
    g.step(1, "Open related pickings via the Pickings button (stock managers).")
    g.step(2, "Validate the transfer when goods are moved.")

  # ===== PART 3: EXAMPLES =====
    g.part(3, "Step-by-Step Examples")

    g.sec("Example 1 - Purchase IT equipment (buy from supplier)")
    g.p("Situation: IT staff needs 3 laptops. They are not in local stock; must be purchased.")
    g.example_box("Steps", [
        "Login as employee. Menu: Purchase Requests > Purchase Requests > New.",
        "Category = IT Category. Requisition date = today.",
        "Products tab: Add a line.",
        "Requisition Action = Purchase Order.",
        "Product = Laptop (must be under an IT product category).",
        "Quantity = 3. Select Vendor(s) on the line.",
        "Click Submit for Approval. Status = Waiting for Review.",
        "Manager receives email. Manager opens PR, reviews, clicks Approve.",
        "Procurement opens PR > Purchase Orders button > confirms PO with supplier.",
        "When delivered, manager sets request to Done.",
    ])

    g.sec("Example 2 - Office supplies from stock (internal transfer)")
    g.p("Situation: Admin needs 50 notebooks available in the main warehouse.")
    g.example_box("Steps", [
        "New Purchase Request. Category = General Category.",
        "Products tab: Product = Notebook, Quantity = 50.",
        "Requisition Action = Internal Picking.",
        "Check Available QTY shows enough stock.",
        "Picking Details: verify operation type and locations (from department).",
        "Submit for Approval.",
        "Manager approves.",
        "Warehouse: open Pickings from the request and validate transfer.",
        "Manager marks PR as Done.",
    ])

    g.add_page()
    g.sec("Example 3 - Partial: part from stock, part to buy")
    g.p("Situation: Need 20 chairs. Only 8 in stock; buy 12 from supplier.")
    g.example_box("Steps", [
        "New PR. Category = General Category.",
        "Add line: Product = Office Chair, Quantity = 20.",
        "Requisition Action = Partial.",
        "System shows Available QTY = 8, Qty to Receive = 8, Qty to Buy = 12.",
        "Select vendor for the purchase portion.",
        "Submit and get manager approval.",
        "After processing: internal move for 8 chairs + purchase order for 12.",
        "Track both from Purchase Orders and Pickings buttons on the PR.",
    ])

    g.sec("Example 4 - New product not in catalog")
    g.p("Situation: Request a new software subscription not listed as a product.")
    g.example_box("Steps", [
        "New PR. Enable checkbox: New Product Request.",
        "Products tab is hidden; use New Products Request tab instead.",
        "Enter Description = Annual CRM subscription.",
        "Cost price = estimated amount. Request qty = 1.",
        "Submit for Approval.",
        "PR Admin or PR IT Admin: open PR in Waiting for Review.",
        "Click Create RFQ. Choose vendor. Click Create RFQ in the popup.",
        "A Purchase Order is created with a text line (no product required).",
        "Continue negotiation and confirmation in Purchase module.",
    ])

    g.sec("Example 5 - Manager checks budget before approval")
    g.p("Situation: Department has a yearly budget; manager must verify before approving.")
    g.example_box("Steps", [
        "Employee submits PR with lines and estimated costs.",
        "Manager opens PR. Budget section is visible (manager or budget access).",
        "Read: Planned Amt, Actual Amt, PR Amount, Remaining Budget.",
        "If Remaining Budget is red, discuss with employee or finance.",
        "Approve only if acceptable; otherwise Reject or ask for changes via messages.",
    ])

    g.sec("Quick reference - Common issues")
    g.li("No products in list: wrong Category (General vs IT) on the request.")
    g.li("Cannot submit empty request: add at least one line (unless New Product Request).")
    g.li("Error on Purchase Order line: product needs a supplier in its settings.")
    g.li("Cannot see other people's requests: normal for standard users.")
    g.li("Create RFQ not visible: only for new-product requests in Waiting for Review.")

    g.ln(6)
    g.set_font("Helvetica", "I", 9)
    g.set_text_color(120, 120, 120)
    g.cell(g.w, 5, "End of guide - Purchase Request module (aafa/purchase_request)", align="C")

    g.output(str(OUT))
    print(f"Generated: {OUT}")


if __name__ == "__main__":
    build()
