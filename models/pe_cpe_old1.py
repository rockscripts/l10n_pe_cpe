# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from .cpe import get_document, get_sign_document, send_sunat_cpe, get_ticket_status, get_response, get_document_invoice, \
    get_status_cdr
from base64 import b64decode, b64encode
from lxml import etree
import pytz
from pytz import timezone
from datetime import datetime
from odoo.exceptions import Warning
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import logging
_logger = logging.getLogger(__name__)


class PeSunatCpe(models.Model):
    _description = 'pe.cpe'
    _name = 'pe.cpe'

    name = fields.Char("Name", default="/")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generate', 'Generated'),
        ('send', 'Send'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False)
    type = fields.Selection([
        ('sync', 'Synchronous'),
        ('rc', 'Daily Summary'),
        ('ra', 'Low communication'),
    ], string="Type", default='sync', states={'draft': [('readonly', False)]})
    date = fields.Date("Date", default=fields.Date.context_today, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env['res.company']._company_default_get('pe.sunat.cpe'))
    xml_document = fields.Text("XML Document", states={'draft': [('readonly', False)]})
    datas = fields.Binary("XML Data", readonly=True)
    datas_fname = fields.Char("XML File Name", readonly=True)
    datas_sign = fields.Binary("XML Sign Data", readonly=True)
    datas_sign_fname = fields.Char("XML Sign File Name", readonly=True)
    datas_zip = fields.Binary("XML Zip Data", readonly=True)
    datas_zip_fname = fields.Char("XML Zip File Name", readonly=True)
    datas_response = fields.Binary("XML Response Data", readonly=True)
    datas_response_fname = fields.Char("XML Response File Name", readonly=True)
    response = fields.Char("Response", readonly=True)
    response_code = fields.Char("Response Code", readonly=True)
    note = fields.Text("Note", readonly=True)
    error_code = fields.Selection("_get_error_code", string="Error Code", readonly=True)
    digest = fields.Char("Digest", readonly=True)
    signature = fields.Text("Signature", readonly=True)
    invoice_ids = fields.One2many("account.invoice", 'pe_cpe_id', string="Invoices", readonly=True)
    ticket = fields.Char("Ticket", readonly=True)
    date_end = fields.Datetime("End Date", states={'draft': [('readonly', False)]})
    send_date = fields.Datetime("Send Date", states={'draft': [('readonly', False)]})
    voided_ids = fields.One2many("account.invoice", "pe_voided_id", string="Voided Invoices")
    summary_ids = fields.One2many("account.invoice", "pe_summary_id", string="Summary Invoices")
    is_voided = fields.Boolean("Is Boided")

    _order = 'date desc, name desc'

    def fix(self, like_name, response_like, mes, start_day, end_day, verify=False):
        from datetime import date
        for x1 in xrange(start_day,end_day):
            fecha_busqueda = date(int(2020), int(mes), int(x1))
            fecha_nueva = date(int(2020), int(8), int(18))

            edocuments = self.env['pe.cpe'].search([("name","ilike",like_name),("response","ilike",response_like),("date","=",fecha_busqueda)], limit=20)
            _logger.warning("FIXING LIST")
            _logger.warning(edocuments)
            if(edocuments):
                for edocument in edocuments:
                    #try:
                    # pe.cpe(512, 471, 422, 384, 339, 298, 248, 203, 160, 116)
                    #if(edocument.id==512):
                        
                        _edocument = self.env['pe.cpe'].browse(edocument.id)                        

                        # reference code 
                        start = '<cbc:ReferenceDate>'
                        end = '</cbc:ReferenceDate>'
                        s = str(edocument.xml_document)
                        ReferenceDate = (s[s.find(start)+len(start):s.rfind(end)])
                        
                        # issue date
                        start = '<cbc:IssueDate>'
                        end = '</cbc:IssueDate>'
                        s = str(edocument.xml_document)
                        IssueDate = (s[s.find(start)+len(start):s.rfind(end)])                        
                        
                        edocument_xml = str(edocument.xml_document).replace(str("<cbc:IssueDate>") + str(IssueDate) + str("</cbc:IssueDate>"), str("<cbc:IssueDate>") + str(ReferenceDate) + str("</cbc:IssueDate>"))    
                        
                                        
                        for account_invoice in edocument.invoice_ids:
                            _account_invoice = account_invoice.browse(account_invoice.id)
                            if(date_invoice.date_invoice!=fecha_busqueda):
                                raise Warning(account_invoice.id)         
                            else:
                                doc_number = _account_invoice.partner_id.doc_number               
                                doc_type = _account_invoice.partner_id.doc_type

                        # issue date
                        start = '<cbc:CustomerAssignedAccountID>'
                        end = '</cbc:CustomerAssignedAccountID>'
                        s = str(edocument.xml_document)
                        edocument_xml = str(edocument_xml).replace(str(start) + str(end),str(start) + str("00000000") + str(end))
                        

                        # issue date
                        start = '<cbc:AdditionalAccountID>'
                        end = '</cbc:AdditionalAccountID>'
                        edocument_xml = str(edocument_xml).replace(str(start) + str(end),"<cbc:AdditionalAccountID>0</cbc:AdditionalAccountID>")

                        # issue date
                        start = '<cbc:AdditionalAccountID>-'
                        end = '</cbc:AdditionalAccountID>'
                        edocument_xml = str(edocument_xml).replace(str(start) + str(end),"<cbc:AdditionalAccountID>0</cbc:AdditionalAccountID>")
                        
                        ReferenceDatesplited = str(ReferenceDate).split("-")
                        fecha_nueva = date(int(ReferenceDatesplited[0]), int(ReferenceDatesplited[1]), int(ReferenceDatesplited[2]))
                        
                        NameSplited = str(edocument.name).split("-")
                        search = str(NameSplited[0]) + str("-") + str(IssueDate).replace("-","") + str("-") + str(NameSplited[2]) 
                        replace = str(NameSplited[0]) + str("-") + str(ReferenceDate).replace("-","") + str("-") + str(NameSplited[2])                
                        edocument_xml = str(edocument_xml).replace(search, replace)
                        
                        _edocument.sudo().update({"name":str(NameSplited[0]) + str("-") + str(ReferenceDate).replace("-","") + str("-") + str(NameSplited[2]) ,"date":fecha_nueva, "xml_document":edocument_xml})
                        
                        _edocument.sudo().action_cancel()
                        _edocument.sudo().action_draft()
                        _edocument.sudo().action_generate()
                        _edocument.sudo().action_send()
                        if(verify):
                            _edocument.sudo().action_done()
                        
                        #raise Warning(_edocument.xml_document)
                    #except:
                    #  raise Warning(edocument.id)

    @api.multi
    def unlink(self):
        for batch in self:
            if batch.name != "/" and batch.state != "draft":
                raise Warning(_('You can only delete sent documents.'))
        return super(PeSunatCpe, self).unlink()

    @api.model
    def _get_error_code(self):
        return self.env['pe.datas'].get_selection("PE.CPE.ERROR")

    @api.one
    def action_draft(self):
        if not self.xml_document and self.type == "sync":
            self._prepare_cpe()
        self.state = 'draft'

    @api.one
    def action_generate(self):
        if not self.xml_document and self.type == "sync":
            self._prepare_cpe()
        elif self.type == "sync" and self.name != "/":
            if self.get_document_name() != self.name:
                self._prepare_cpe()
        if self.type == "sync":
            self._sign_cpe()
        self.state = 'generate'

    @api.one
    def action_send(self):
        state = self.send_cpe()
        if state:
            self.state = state

    @api.one
    def action_verify(self):
        self.state = 'verify'

    @api.one
    def action_done(self):
        if self.type in ['rc', 'ra']:
            status = self.get_sunat_ticket_status()
            if status == 'done' and self.type == 'rc':
                if self.is_voided == False:
                    for invoice_id in self.summary_ids.filtered(lambda inv: inv.state in ['cancel', 'annul']):
                        pe_summary_id = self.env['pe.cpe'].get_cpe_async("rc", invoice_id)
                        invoice_id.pe_summary_id = pe_summary_id.id
                        if not pe_summary_id.is_voided:
                            pe_summary_id.is_voided = True
            if status:
                self.state = status
        else:
            self.state = 'done'

    @api.one
    def action_cancel(self):
        self.state = 'cancel'

    @api.model
    def create_from_invoice(self, invoice_id):
        vals = {}
        vals['invoice_ids'] = [(4, invoice_id.id)]
        vals['type'] = 'sync'
        vals['company_id'] = invoice_id.company_id.id
        res = self.create(vals)
        return res

    @api.model
    def get_cpe_async(self, type, invoice_id):
        res = None
        company_id = invoice_id.company_id.id
        date_invoice = invoice_id.date_invoice
        cpe_ids = self.search([('state', '=', 'draft'), ('type', '=', type), ('date', '=', date_invoice),
                               ('name', '=', "/"), ('company_id', '=', company_id)], order="date DESC")
        for cpe_id in cpe_ids:
            if cpe_id and len(cpe_id.summary_ids.ids) < 500:
                res = cpe_id
                break
        if not res:
            vals = {}
            vals['type'] = type
            vals['date'] = date_invoice
            vals['company_id'] = company_id
            res = self.create(vals)
        return res

    @api.multi
    def get_document_name(self):
        self.ensure_one()
        ruc = self.company_id.partner_id.doc_number
        if self.type == "sync":
            doc_code = "-%s" % self.invoice_ids[0].journal_id.pe_invoice_code
            if self.name:
                number = self.name
            else:
                number = self.invoice_ids[0].move_name
        else:
            doc_code = ""
            number = self.name or ""
        return "%s%s-%s" % (ruc, doc_code, number)

    @api.multi
    def prepare_sunat_auth(self):
        self.ensure_one()
        res = {}
        res['ruc'] = self.company_id.partner_id.doc_number
        res['username'] = self.company_id.pe_cpe_server_id.user
        res['password'] = self.company_id.pe_cpe_server_id.password
        res['url'] = self.company_id.pe_cpe_server_id.url
        return res

    @api.one
    def _prepare_cpe(self):
        if not self.xml_document:
            file_name = self.get_document_name()
            xml_document = get_document(self)
            self.xml_document = xml_document
            self.datas = b64encode(xml_document)
            self.datas_fname = file_name + ".xml"

    @api.one
    def _sign_cpe(self):
        file_name = self.get_document_name()
        if not self.xml_document:
            self._prepare_cpe()
        if self.xml_document.encode('utf-8') != b64decode(self.datas):
            self.datas = b64encode(self.xml_document.encode('utf-8'))
            # self.datas_fname = file_name+".xml"
        key = self.company_id.pe_certificate_id.key
        crt = self.company_id.pe_certificate_id.crt
        self.datas_sign = b64encode(get_sign_document(self.xml_document, key, crt))
        self.datas_sign_fname = file_name + ".xml"
        self.get_sign_details()

    @api.multi
    def send_cpe(self):
        res = None
        self.ensure_one()
        date_parts = str(self.date).split("-")
        self.send_date = datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]), 23, 0) # fields.Datetime.context_timestamp(self.env.user, datetime.now()).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        local_date = datetime.strptime(self.send_date.strftime('%Y-%m-%d %H:%M:%S'), "%Y-%m-%d %H:%M:%S").date().strftime("%Y-%m-%d")
        if self.type == "sync" and self.name == "/":
            self.name = self.invoice_ids[0].number
        elif self.type == "ra" and self.name == "/":
            self.name = self.env['ir.sequence'].with_context(ir_sequence_date=local_date).next_by_code(
                'pe.sunat.cpe.ra')
        elif self.type == "rc" and self.name == "/":
            self.name = self.env['ir.sequence'].with_context(ir_sequence_date=local_date).next_by_code(
                'pe.sunat.cpe.rc')
        file_name = self.get_document_name()
        if self.type in ["rc", "ra"]:
            self._prepare_cpe()
            self._sign_cpe()
            self.datas_fname = file_name + ".xml"
            self.datas_sign_fname = file_name + ".xml"
        client = self.prepare_sunat_auth()
        document = {}
        document['document_name'] = file_name
        document['type'] = self.type
        document['xml'] = b64decode(self.datas_sign)
        self.datas_zip, response_status, response, response_data = send_sunat_cpe(client, document)
        self.datas_zip_fname = file_name + ".zip"
        if response_status:
            res = "verify"
            if self.type == "sync":
                self.datas_response = response_data
                new_state = self.get_response_details()
                self.datas_response_fname = 'R-%s.zip' % file_name
                res = new_state or res
            else:
                self.ticket = response_data
        else:
            res = "send"
            self.response = response.get("faultcode")
            self.note = response.get("faultstring")
            if response.get("faultcode"):
                code = len(response.get("faultcode").split(".")) >= 2 and "%04d" % int(
                    response.get("faultcode").split(".")[-1].encode('utf-8')) or False
                self.response_code = code
                #self.error_code = code
        return res

    @api.multi
    def get_sign_details(self):
        self.ensure_one()
        vals = {}
        tag = etree.QName('http://www.w3.org/2000/09/xmldsig#', 'DigestValue')
        xml_sign = b64decode(self.datas_sign)
        digest = etree.fromstring(xml_sign).find('.//' + tag.text)
        if digest != -1:
            self.digest = digest.text
        tag = etree.QName('http://www.w3.org/2000/09/xmldsig#', 'SignatureValue')
        sign = etree.fromstring(xml_sign).find('.//' + tag.text)
        if sign != -1:
            self.signature = sign.text

    @api.multi
    @api.depends('datas_response')
    def get_response_details(self):
        self.ensure_one()
        vals = {}
        state = self.state
        if self.datas_response:
            try:
                file_name = self.get_document_name()
                xml_response = get_response({'file': self.datas_response, 'name': 'R-%s.xml' % file_name})
                sunat_response = etree.fromstring(xml_response)
                cbc = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
                tag = etree.QName(cbc, 'ResponseDate')
                date = sunat_response.find('.//' + tag.text)
                tag = etree.QName(cbc, 'ResponseTime')
                time = sunat_response.find('.//' + tag.text)
                if time != -1 and date != -1:
                    self.date_end = fields.Datetime.context_timestamp(self.env.user, datetime.now()).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                tag = etree.QName(cbc, 'ResponseCode')
                code = sunat_response.find('.//' + tag.text)
                res_code = ""
                if code != -1:
                    res_code = "%04d" % int(code.text)
                    self.response_code = res_code
                    if res_code == "0000":
                        self.error_code = False
                        state = "done"
                tag = etree.QName(cbc, 'Description')
                description = sunat_response.find('.//' + tag.text)
                res_desc = ""
                if description != -1:
                    res_desc = description.text
                self.response = "%s - %s" % (res_code, res_desc)
                notes = sunat_response.xpath(".//cbc:Note", namespaces={
                    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'})
                res_note = ""
                for note in notes:
                    res_note += note.text
                self.note = res_note
            except:
                pass
        return state

    @api.one
    def generate_cpe(self):
        self._prepare_cpe()
        self._sign_cpe()
        self.state = "generate"

    @api.multi
    def get_sunat_ticket_status(self):
        self.ensure_one()
        client = self.prepare_sunat_auth()
        response_status, response, response_file = get_ticket_status(self.ticket, client)
        state = None
        if response_status:
            file_name = self.get_document_name()
            self.datas_response = response_file
            self.datas_response_fname = 'R-%s.zip' % file_name
            state = self.get_response_details()
        else:
            res = "send"
            self.response = response.get("faultcode", False)
            self.note = response.get("faultstring", False)
            if response.get("faultcode", False):
                code = len(response.get("faultcode").split(".")) >= 2 and "%04d" % int(
                    response.get("faultcode").split(".")[-1].encode('utf-8')) or False
                self.error_code = code
        if self.type == "rc":
            for invoice_id in self.summary_ids:
                if invoice_id.pe_cpe_id.name == "/":
                    invoice_id.pe_cpe_id.name = invoice_id.move_name
                invoice_id.pe_cpe_id.response = self.response
                if state and response_status:
                    invoice_id.pe_cpe_id.state = state
        return state

    @api.one
    def action_document_status(self):
        client = self.prepare_sunat_auth()
        name = self.get_document_name()
        response_status, response, response_file = get_status_cdr(name, client)
        state = None
        if response_status:
            self.note = "%s - %s" % (
            response['statusCdr'].get('statusCode', ""), response['statusCdr'].get('statusMessage', ""))
            if response_file:
                self.datas_response = response_file
                self.datas_response_fname = 'R-%s.zip' % name
                state = self.get_response_details()
                if state:
                    self.state = state
        else:
            self.response = response.get("faultcode", False)
            self.note = response.get("faultstring") or str(response)
            if response.get("faultcode"):
                try:
                    code = len(response.get("faultcode").split(".")) >= 2 and "%04d" % int(
                        response.get("faultcode").split(".")[-1].encode('utf-8')) or False
                    self.error_code = code
                except:
                    pass

    @api.multi
    def send_rc(self):
        cpe_ids = self.search([('state', 'in', ['draft', 'generate', 'verify']), ('type', 'in', ['rc'])])
        for cpe_id in cpe_ids:
            if cpe_id.state == 'verify':
                cpe_id.action_done()
            else:
                cpe_id.action_generate()
                cpe_id.action_send()

    @api.multi
    def send_ra(self):
        cpe_ids = self.search([('state', 'in', ['draft', 'generate', 'verify']), ('type', 'in', ['ra'])])
        for cpe_id in cpe_ids:
            if cpe_id.state == 'verify':
                cpe_id.action_done()
            else:
                check = True
                for invoice_id in cpe_id.invoice_ids:
                    if invoice_id.pe_invoice_code in ["03"] and invoice_id.origin_doc_code in ["03"]:
                        if invoice_id.pe_summary_id.state not in ['verify', 'done']:
                            check = False
                            break
                if check:
                    cpe_id.action_generate()
                    cpe_id.action_send()

    @api.multi
    def send_async_cpe(self):
        cpe_ids = self.search([('state', 'in', ['generate', 'send']), ('type', 'in', ['sync'])])
        for cpe_id in cpe_ids:
            if cpe_id.invoice_ids:
                if cpe_id.send_date and cpe_id.invoice_ids[0].pe_invoice_code not in ["03"] and cpe_id.invoice_ids[
                    0].origin_doc_code not in ["03"]:
                    cpe_id.action_document_status()
                if cpe_id.state != 'done':
                    if cpe_id.invoice_ids[0].pe_invoice_code not in ["03"] and cpe_id.invoice_ids[
                        0].origin_doc_code not in ["03"]:
                        cpe_id.action_generate()
                        cpe_id.action_send()







