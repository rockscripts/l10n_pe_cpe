# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_cpe = fields.Boolean("Is CPE")
    is_synchronous = fields.Boolean("Is synchronous")
    is_homologation = fields.Boolean("Is homologation")

class AccountTax(models.Model):
    _inherit = 'account.tax'
    
    pe_tax_type = fields.Many2one(comodel_name="pe.datas", string="Tax Type",
                                  domain="[('table_code','=', 'PE.CPE.CATALOG5')]")
    pe_tax_code = fields.Selection("_get_pe_tax_code", string="Tax Code")
    
    pe_tier_range = fields.Selection(selection= "_get_pe_tier_range", string="Type of System", 
                                     help="Type of system to the ISC")
    @api.model
    def _get_pe_tier_range(self):
        return self.env['pe.datas'].get_selection("PE.CPE.CATALOG8")
    
    @api.model
    def _get_pe_tax_code(self):
        return self.env['pe.datas'].get_selection("PE.CPE.CATALOG5")
    
    @api.onchange('pe_tax_type')
    def onchange_pe_tax_type(self):
        if self.pe_tax_type:
            self.pe_tax_code = self.pe_tax_type.code