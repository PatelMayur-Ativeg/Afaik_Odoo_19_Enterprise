# -*- coding: utf-8 -*-

# Shared selection for account.move / account.payment transaction_type.
TRANSACTION_TYPE_SELECTION = [
    # Accounting documents (from account.move.move_type)
    ("out_invoice", "Customer Invoice"),
    ("out_refund", "Customer Credit Note"),
    ("in_invoice", "Vendor Bill"),
    ("in_refund", "Vendor Credit Note"),
    ("out_receipt", "Sales Receipt"),
    ("in_receipt", "Purchase Receipt"),
    ("entry", "Journal Entry"),
    # Aafaq importer queue record types that create journal entries
    ("journal_entries", "Finacle Loader (FL)"),
    ("adj_entries", "Adjustment Entries (AE)"),
    # Payments
    ("customer_payment", "Customer Payment"),
    ("customer_refund", "Customer Refund"),
    ("vendor_payment", "Vendor Payment"),
    ("vendor_refund", "Vendor Refund"),
    ("internal_transfer", "Internal Transfer"),
]

# Importer queue.record_type values that map onto transaction_type as-is.
IMPORTER_TRANSACTION_TYPES = frozenset({"journal_entries", "adj_entries"})

# Manual / standard documents: move_type key == transaction_type key.
MOVE_TYPE_TRANSACTION_TYPES = frozenset({
    "out_invoice",
    "out_refund",
    "in_invoice",
    "in_refund",
    "out_receipt",
    "in_receipt",
    "entry",
})
