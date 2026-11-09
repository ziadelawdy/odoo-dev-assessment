{
    'name': 'Dynamic Trial Balance',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Wizard-driven trial balance with Initial / Movement / End debit, credit and balance',
    'author': 'Ziad Elawdy',
    'license': 'LGPL-3',
    'depends': ['account_reports'],
    'data': [
        'security/ir.access.csv',
        'data/dynamic_trial_balance_report.xml',
        'data/pdf_export_templates.xml',
        'wizard/dynamic_trial_balance_wizard_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'azk_dynamic_trial_balance/static/src/components/**/*',
        ],
        'web.assets_tests': [
            'azk_dynamic_trial_balance/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
