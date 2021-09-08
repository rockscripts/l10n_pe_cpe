# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Company(models.Model):
    _inherit = "res.company"

    pe_is_sync = fields.Boolean("Is Synchronous", default= True)
    pe_certificate_id = fields.Many2one(comodel_name="pe.certificate", string="Certificate", 
                                     domain="[('state','=','done')]")
    pe_cpe_server_id = fields.Many2one(comodel_name="pe.server", string="Server", 
                                     domain="[('state','=','done')]")
    sunat_resolution_type= fields.Char("Resolution Type")
    sunat_resolution_number= fields.Char("Resolution Number")
    sunat_amount = fields.Float(string="Amount", digits=(16,2), default=700)