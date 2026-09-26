# -*- coding: utf-8 -*-
{
    "name": "Aafaq Deferred Reschedule",
    "version": "19.0.1.3.0",
    "category": "Accounting/Accounting",
    "summary": "Reschedule deferred end dates on posted bills and invoices",
    "author": "Aafaq",
    "depends": ["account_accountant"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/account_deferred_reschedule_wizard_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
