# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class AccountInvoiceRefund(models.TransientModel):
    _inherit = "account.invoice.refund"
    
    pe_debit_note_code = fields.Selection(selection="_get_pe_debit_note_type", string="Dedit Note Code")
    pe_credit_note_code = fields.Selection(selection="_get_pe_crebit_note_type", string="Credit Note Code")
    
    @api.model
    def _get_pe_crebit_note_type(self):
        return self.env['pe.datas'].get_selection("PE.CPE.CATALOG9")
    
    @api.model
    def _get_pe_debit_note_type(self):
        return self.env['pe.datas'].get_selection("PE.CPE.CATALOG10")

    @api.multi
    def invoice_refund(self):
        res = super(AccountInvoiceRefund, self).invoice_refund()
        if self.env.context.get("is_pe_debit_note", False):
            invoice_domain = res['domain']
            if invoice_domain:
                del invoice_domain[0]
                res['domain'] = invoice_domain
        return res