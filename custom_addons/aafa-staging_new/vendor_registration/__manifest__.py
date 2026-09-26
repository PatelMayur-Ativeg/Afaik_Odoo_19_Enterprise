# -*- coding: utf-8 -*-

{
"name" :  "vendor_registration",
"summary":  """vendor_registration""",
"category":  "Website",
"version" :  "1.1",
"description":  """vendor_registration""",
"depends":  [
             'base',
             'purchase',
             # 'website',
             'account',
             'user_notification',
             'mail',
             'auth_signup',
             'portal',
             'documents',
            ],
  "data":  [
     'security/security.xml',
     'security/ir.model.access.csv',
     'data/ir_sequence_data.xml',
     'wizards/reject_reason_view.xml',
     'views/registration.xml',
     'views/menus.xml',
     'views/portal_register_templates.xml',
     'views/res_bank_view.xml',
     'views/partner.xml',
    ],
  "application":  True,
  "installable":  True,
  "auto_install":  False,

}
