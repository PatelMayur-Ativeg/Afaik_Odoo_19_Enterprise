# -*- coding: utf-8 -*-
{
    "name": "Multi Invoice Payment",
    "summary": "Pay and reconcile multiple customer invoices or vendor bills in one payment",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "license": "OPL-1",
    "author": "Ativeg Technology",
    "website": "https://www.ativeg.tech",
    "description": """
Multi Invoice Payment
=====================
Register one payment against multiple open invoices or bills, with full or
partial reconciliation. Supports customer and vendor documents, credit notes,
with a manually entered payment amount as in standard Odoo.
    """,
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_payment_invoice_views.xml",
        "views/multiinvoice_payment_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mai_multiinvoice_payment/static/src/payment_embedded/payment_embedded.scss",
            "mai_multiinvoice_payment/static/src/payment_embedded/view_embedder.xml",
            "mai_multiinvoice_payment/static/src/payment_embedded/payment_embedded_list_widget.xml",
            "mai_multiinvoice_payment/static/src/payment_embedded/view_embedder.js",
            "mai_multiinvoice_payment/static/src/payment_embedded/embedded_list_view.js",
            "mai_multiinvoice_payment/static/src/payment_embedded/payment_invoice_embedded_list.js",
            "mai_multiinvoice_payment/static/src/payment_embedded/payment_embedded_list_widget.js",
        ],
    },
    "images": ["static/description/main_screenshot.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
}
