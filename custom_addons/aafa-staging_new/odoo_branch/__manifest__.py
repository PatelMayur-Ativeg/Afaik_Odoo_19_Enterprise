# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Multiple Branch(Unit) Operation Setup for All Applications Odoo',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Multiple Branch Operation on Sales, Purchases,Invoicing, Voucher, Payment, Accounting Reports for single company',
    "description": """
       Multiple Unit operation management for single company Multiple Branch management for single company
      
    """,
    'author': 'Codisoft',
    'website': 'http://www.Codisoft.com',
    "price": 129.00,
    "currency": 'EUR',
    'depends': ['base', 'sale_management', 'purchase', 'stock', 'account', 'purchase_stock','sale_stock','currency_rate_live','account_asset',],
    'data': [
        'security/branch_security.xml',
        'security/ir.model.access.csv',
        'views/res_branch_view.xml',
        'views/inherited_res_users.xml',
        'views/inherited_sale_order.xml',
        'views/inherited_stock_picking.xml',
        'views/inherited_stock_move.xml',
        'views/inherited_account_invoice.xml',
        'views/inherited_purchase_order.xml',
        'views/inherited_stock_warehouse.xml',
        'views/inherited_stock_location.xml',
        # 'views/inherited_account_bank_statement.xml',
        'wizard/inherited_account_payment.xml',
        # 'views/inherited_stock_inventory.xml',
        'views/inherited_product.xml',
        # 'views/inherited_partner.xml',
        'views/assets.xml',
    ],
    'demo': [],
    'test': [],
    "auto_install": False,
    "installable": True,
    "application": True,
    'live_test_url': 'https://youtu.be/f-nqKb_jELg',
    "images": ['static/description/Banner.png'],
    'post_init_hook': 'post_init_hook',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
