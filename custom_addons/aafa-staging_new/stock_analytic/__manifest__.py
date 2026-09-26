
{
    "name": "Stock Analytic",
    "summary": "Adds analytic distribution in stock move",
    "version": "1.0",
    "author": "Julius Network Solutions, ClearCorp, OpenSynergy Indonesia, Hibou Corp., Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/account-analytic",
    "category": "Warehouse Management",
    "license": "AGPL-3",
    "depends": ["stock_account", "analytic"],
    "data": [
        "views/stock_move_views.xml",
        "views/stock_scrap_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_picking_views.xml",
    ],
    "description": """
    <h2>Stock Analytic</h2>
    <p>Adds analytic distribution in stock move.</p>
    """,
    "auto_install": False,
    "installable": True,
    "application": True,
}
