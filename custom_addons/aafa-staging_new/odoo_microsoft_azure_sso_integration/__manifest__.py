{
    'name': 'Microsoft Azure OAuth2 SSO Integration',
    'version': '1.0',
    'category': 'Extra Tools',
    'sequence': 1,

    'price': 30.00,
    'license': 'OPL-1',
    'currency': 'USD',

    'author': 'Techspawn Solutions Pvt Ltd',
    'website': 'http://www.techspawn.com',
    'summary': """Odoo Microsoft Azure SSO Integration module allows instant and secure login with the help of Microsoft SSO and OAuth2
 """,
    'description': """This module allows you to sync Microsoft users with Odoo seamlessly.""",
    'demo_xml': [],
    'update_xml': [],
    'depends': ['auth_oauth'],
    'data': ['data/data.xml',
             'views/oauth_provider_view.xml'
             ],
    'images': ['static/description/azure_banner_img_V16_2.gif'],
    'js': [],
    'application': True,
    'installable': True,
    'auto_install': False,
}
