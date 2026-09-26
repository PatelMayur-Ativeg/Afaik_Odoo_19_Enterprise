# -*- coding: utf-8 -*-
{
    "name": "Advanced Comma Search",
    "summary": "Configure comma-separated search on any model and field",
    "description": """
Allow comma-separated values in the search bar (e.g. SO001,SO002).
Configure models and fields under Settings > Technical > User Interface > Advanced Search.
    """,
    "author": "",
    "website": "",
    "category": "Hidden/Tools",
    "version": "1.1.0",
    "depends": ["web"],
    "data": [
        "security/ir.model.access.csv",
        "views/advanced_search_config_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sale_adavance_search/static/src/js/search_model.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
