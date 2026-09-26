# -*- coding: utf-8 -*-
{
    "name": "Document Expiry and Notify",
    "summary": "Set Expiry Date for Document and Notfiy",
    "version": "1.0",
    'category': 'Productivity/Documents',
    'author': "Rinoy",
    'maintainer': "Rinoy",

    "depends": ["web", "documents", "hr"],
    "data": [
        'views/email_template.xml',
        'views/documents_views.xml',
        'views/cron_jobs.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         'document_expiry/static/src/xml/document.xml',
    #     ],
    # },
    "installable": True,
}
