# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    @api.multi
    def create_invoices(self):
        res = super(SaleAdvancePaymentInv, self).create_invoices()
        order = self.env['sale.order'].browse(self._context.get('active_ids', []))
        for invoice_id in order.invoice_ids:
            invoice_id.with_context(force_pe_journal=True)._onchange_partner_id()
            invoice_id.pe_license_plate = order.pe_license_plate
            for line in invoice_id.invoice_line_ids:
                if line.product_id:
                    sale_lines = order.mapped('order_line').filtered(lambda so: so.product_id.id == line.product_id.id)
                    if len(sale_lines)>1:
                        line.pe_license_plate = sale_lines[0].pe_license_plate
                    else:
                        line.pe_license_plate = sale_lines.pe_license_plate
        return res
    