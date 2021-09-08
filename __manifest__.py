# -*- coding: utf-8 -*-
{
    'name': "Peruvian Electronic Voucher",

    'summary': """
        Peruvian Electronic Payment Voucher
    """,

    'description': """
        Peruvian Electronic Payment Voucher
    """,

    'author': "techruna",
    'website': "http://www.techruna.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.2',

    # any module necessary for this one to work correctly
    'depends': [
        'account',
        'sale',
        'account_cancel',
        'website',
        'amount_to_text',
        'l10n_pe_vat',
        'l10n_pe_datas',
        'l10n_pe_server',
        'l10n_pe_certificate',
        'l10n_pe_invoice',
        'l10n_pe_extend',
        'account_annul'
    ],

    # always loaded
    'data': [
        #'data/pe.datas.csv',
        'security/pe_cpe_security.xml',
        'security/ir.model.access.csv', 
        'data/pe.datas.catalog59.xml',       
        'views/account_invoice_view.xml',
        'views/pe_cpe_view.xml',
        'views/account_view.xml',
        'views/company_view.xml',
        'views/report_invoice.xml',
        'views/product_view.xml',
        'views/sale_view.xml',
        'wizard/account_invoice_debit_view.xml',
        'views/pe_cpe_template.xml',
        'data/pe_cpe_data.xml',
        'data/invoice_data_action.xml',
        'views/res_config_setting_view.xml',        
    ],
    
    # only loaded in demonstration mode
    'demo': [
    ],
}