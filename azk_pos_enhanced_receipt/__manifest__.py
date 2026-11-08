{
    'name': 'POS Enhanced Receipt Layout',
    'version': '20.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Configurable branded POS receipt: logo, company info, customer details, lines table',
    'author': 'Ziad Elawdy',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_config_views.xml',
        'receipt/pos_order_receipt.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'azk_pos_enhanced_receipt/static/src/**/*',
        ],
        'web.assets_tests': [
            'azk_pos_enhanced_receipt/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
