# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.addons import decimal_precision as dp


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    pe_license_plate = fields.Char("License Plate", readonly=True, states={'draft': [('readonly', False)]}, copy=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    pe_license_plate = fields.Char("License Plate", readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    
    @api.onchange('pe_license_plate')
    def onchange_pe_license_plate(self):
        for line in self.order_line:
            if line.product_id.require_plate:
                line.pe_license_plate = self.pe_license_plate