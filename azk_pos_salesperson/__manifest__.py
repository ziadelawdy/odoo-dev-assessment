{
    'name': 'POS Salesperson Assignment',
    'version': '20.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Assign salespersons to POS order lines, offline, with receipt printing',
    'author': 'Ziad Elawdy',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'hr'],
    'data': [
        'security/ir.access.csv',
        'views/pos_sale_person_views.xml',
        'views/pos_config_views.xml',
        'views/pos_order_views.xml',
        'views/salesperson_report_views.xml',
        'receipt/pos_order_receipt.xml',
    ],
    'demo': [
        'demo/pos_sale_person_demo.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'azk_pos_salesperson/static/src/**/*',
        ],
        'web.assets_tests': [
            'azk_pos_salesperson/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
