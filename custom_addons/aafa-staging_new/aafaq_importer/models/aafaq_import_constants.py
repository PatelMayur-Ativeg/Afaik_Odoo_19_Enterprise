RECORD_TYPE_SELECTION = [
    ("customer", "Financing Customers"),
    ("customer_wakala_asset", "Wakala Assets Customers"),
    ("customer_wakala_lib", "Wakala Liability Customers"),
    ("journal_entries", "Journal Entries (JV)"),
    ("adj_entries", "Adjustment Entries (AE)"),
    ("coa", "Chart of Accounts"),
]

RECORD_TYPE_SEQUENCE_MAP = {
    "customer": "aafaq.import.customer",
    "customer_wakala_asset": "aafaq.import.customer.wakala_asset",
    "customer_wakala_lib": "aafaq.import.customer.wakala_lib",
    "journal_entries": "netsuite.import.journal.entries",
    "adj_entries": "netsuite.import.adj.entries",
    "coa": "aafaq.import.coa",
}

RECORD_TYPE_JOURNAL_MAP = {
    "journal_entries": "Finnacle Loader",
    "adj_entries": "Adjusting Entries",
}

# Incoming mail for these alias types is stored on aafaq.import.held.mail
# until the nightly cron or a manual Process Held Emails action.
HELD_EMAIL_RECORD_TYPES = frozenset({"journal_entries", "adj_entries"})

RECORD_TYPE_ALIAS_NAME = {
    "customer": "aafaq-customers",
    "customer_wakala_asset": "aafaq-wakala-assets",
    "customer_wakala_lib": "aafaq-wakala-liability",
    "journal_entries": "aafaq-journal-entries",
    "adj_entries": "aafaq-adjustment-entries",
    "coa": "aafaq-chart-of-accounts",
}

IMPORT_FILE_EXTENSIONS = (".xlsx", ".xls", ".csv")
IMPORT_FILE_PRIORITY = {".xlsx": 3, ".xls": 2, ".csv": 1}

# Template "Odoo Type" labels -> account.account.account_type
COA_ACCOUNT_TYPE_MAP = {
    "receivable": "asset_receivable",
    "bank and cash": "asset_cash",
    "current assets": "asset_current",
    "non-current assets": "asset_non_current",
    "non current assets": "asset_non_current",
    "prepayments": "asset_prepayments",
    "fixed assets": "asset_fixed",
    "payable": "liability_payable",
    "credit card": "liability_credit_card",
    "current liabilities": "liability_current",
    "non-current liabilities": "liability_non_current",
    "non current liabilities": "liability_non_current",
    "equity": "equity",
    "current year earnings": "equity_unaffected",
    "income": "income",
    "other income": "income_other",
    "expenses": "expense",
    "expense": "expense",
    "other expenses": "expense_other",
    "depreciation": "expense_depreciation",
    "cost of revenue": "expense_direct_cost",
    "off-balance sheet": "off_balance",
    "off balance sheet": "off_balance",
}
