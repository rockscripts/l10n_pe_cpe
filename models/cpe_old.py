# -*- coding: utf-8 -*-
from lxml import etree
from io import StringIO, BytesIO
import xmlsec
from collections import OrderedDict
from pysimplesoap.client import SoapClient, SoapFault, fetch
import base64, zipfile
from odoo import _
from odoo.exceptions import UserError
from datetime import datetime
from pysimplesoap.simplexml import SimpleXMLElement
import logging
from odoo.tools import float_is_zero, float_round
from tempfile import gettempdir
import socket
from binascii import hexlify

log = logging.getLogger(__name__)


class CPE:

    def __init__(self):
        self._cac = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
        self._cbc = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
        self._ccts = 'urn:un:unece:uncefact:documentation:2'
        self._ds = 'http://www.w3.org/2000/09/xmldsig#'
        self._ext = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
        self._qdt = 'urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2'
        self._sac = 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1'
        self._udt = 'urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2'
        self._xsi = 'http://www.w3.org/2001/XMLSchema-instance'
        self._root = None

    def _getX509Template(self, content):
        tag = etree.QName(self._ds, 'Signature')
        signature = etree.SubElement(content, tag.text, Id='signatureRECORD', nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'SignedInfo')
        signed_info = etree.SubElement(signature, tag.text, nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'CanonicalizationMethod')
        etree.SubElement(signed_info, tag.text, Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315',
                         nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'SignatureMethod')
        etree.SubElement(signed_info, tag.text, Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1',
                         nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'Reference')
        reference = etree.SubElement(signed_info, tag.text, URI='', nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'Transforms')
        transforms = etree.SubElement(reference, tag.text, nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'Transform')
        etree.SubElement(transforms, tag.text, Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature',
                         nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'DigestMethod')
        etree.SubElement(reference, tag.text, Algorithm='http://www.w3.org/2000/09/xmldsig#sha1',
                         nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'DigestValue')
        etree.SubElement(reference, tag.text, nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'SignatureValue')
        etree.SubElement(signature, tag.text, nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'KeyInfo')
        key_info = etree.SubElement(signature, tag.text, nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'X509Data')
        data = etree.SubElement(key_info, tag.text, nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'X509SubjectName')
        etree.SubElement(data, tag.text, nsmap={'ds': tag.namespace})
        tag = etree.QName(self._ds, 'X509Certificate')
        etree.SubElement(data, tag.text, nsmap={'ds': tag.namespace})

    def _getUBLVersion(self, version=None, customization=None):
        tag = etree.QName(self._cbc, 'UBLVersionID')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = version or '2.1'
        tag = etree.QName(self._cbc, 'CustomizationID')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = customization or '2.0'

    def _getUBLVersion21(self, version=None, customization=None):
        tag = etree.QName(self._cbc, 'UBLVersionID')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = version or '2.1'
        tag = etree.QName(self._cbc, 'CustomizationID')
        etree.SubElement(self._root, tag.text, schemeAgencyName='PE:SUNAT',
                         nsmap={'cbc': tag.namespace}).text = customization or '2.0'

    def _getDocumentDetail21(self, invoice_id):
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = invoice_id.move_name or ''
        tag = etree.QName(self._cbc, 'IssueDate')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = datetime.strptime(
            invoice_id.pe_invoice_date.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        tag = etree.QName(self._cbc, 'IssueTime')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = datetime.strptime(
            invoice_id.pe_invoice_date.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S')
        if invoice_id.pe_invoice_code in ('01', '03'):
            tag = etree.QName(self._cbc, 'InvoiceTypeCode')
            etree.SubElement(self._root, tag.text, listID=invoice_id.pe_sunat_transaction51, listAgencyName='PE:SUNAT',
                             listName='Tipo de Documento', listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01',
                             nsmap={'cbc': tag.namespace}).text = invoice_id.pe_invoice_code
        for line in invoice_id.pe_additional_property_ids:
            tag = etree.QName(self._cbc, 'Note')
            etree.SubElement(self._root, tag.text, languageLocaleID=line.code,
                             nsmap={'cbc': tag.namespace}).text = line.value

        tag = etree.QName(self._cbc, 'DocumentCurrencyCode')
        etree.SubElement(self._root, tag.text, listID='ISO 4217 Alpha', listName='Currency',
                         listAgencyName='United Nations Economic Commission for Europe',
                         nsmap={'cbc': tag.namespace}).text = invoice_id.currency_id.name
        tag = etree.QName(self._cbc, 'LineCountNumeric')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = str(
            len(invoice_id.invoice_line_ids))
        if invoice_id.pe_invoice_code in ('01', '03'):
            sale_ids = invoice_id.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
            for sale in sale_ids:
                tag = etree.QName(self._cac, 'OrderReference')
                order = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'ID')
                etree.SubElement(order, tag.text,
                                 nsmap={'cbc': tag.namespace}).text = sale.client_order_ref or sale.name
                break

            if invoice_id.env.context.get('despatch_numbers') and invoice_id.env.context.get('despatch_numbers',
                                                                                             {}).get(invoice_id.id):
                for despatch_number in invoice_id.env.context.get('despatch_numbers', {}).get(invoice_id.id, []):
                    tag = etree.QName(self._cac, 'DespatchDocumentReference')
                    despatch = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
                    tag = etree.QName(self._cbc, 'ID')
                    etree.SubElement(despatch, tag.text, nsmap={'cbc': tag.namespace}).text = despatch_number
                    tag = etree.QName(self._cbc, 'DocumentTypeCode')
                    etree.SubElement(despatch, tag.text, listAgencyName='PE:SUNAT', listName='Tipo de Documento',
                                     listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01',
                                     nsmap={'cbc': tag.namespace}).text = '09'

            if invoice_id.pe_additional_type:
                tag = etree.QName(self._cac, 'AdditionalDocumentReference')
                additional = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'ID')
                etree.SubElement(additional, tag.text,
                                 nsmap={'cbc': tag.namespace}).text = invoice_id.pe_additional_number
                tag = etree.QName(self._cbc, 'DocumentTypeCode')
                etree.SubElement(additional, tag.text,
                                 nsmap={'cbc': tag.namespace}).text = invoice_id.pe_additional_type

    def _getSignature(self, invoice_id):
        tag = etree.QName(self._cac, 'Signature')
        signature = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(signature, tag.text, nsmap={
            'cbc': tag.namespace}).text = invoice_id._name == 'pe.cpe' and invoice_id.name or invoice_id.move_name
        tag = etree.QName(self._cac, 'SignatoryParty')
        party = etree.SubElement(signature, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'PartyIdentification')
        identification = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(identification, tag.text,
                         nsmap={'cbc': tag.namespace}).text = invoice_id.company_id.partner_id.doc_number
        tag = etree.QName(self._cac, 'PartyName')
        name = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'Name')
        etree.SubElement(name, tag.text,
                         nsmap={'cbc': tag.namespace}).text = invoice_id.company_id.partner_id.legal_name
        tag = etree.QName(self._cac, 'DigitalSignatureAttachment')
        attachment = etree.SubElement(signature, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'ExternalReference')
        reference = etree.SubElement(attachment, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'URI')
        etree.SubElement(reference, tag.text, nsmap={'cbc': tag.namespace}).text = '#signatureRECORD'

    def _getCompany(self, invoice_id):
        tag = etree.QName(self._cac, 'AccountingSupplierParty')
        supplier = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'CustomerAssignedAccountID')
        etree.SubElement(supplier, tag.text,
                         nsmap={'cbc': tag.namespace}).text = invoice_id.company_id.partner_id.doc_number
        tag = etree.QName(self._cbc, 'AdditionalAccountID')
        etree.SubElement(supplier, tag.text,
                         nsmap={'cbc': tag.namespace}).text = invoice_id.company_id.partner_id.doc_type
        tag = etree.QName(self._cac, 'Party')
        party = etree.SubElement(supplier, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'PartyName')
        party_name = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'Name')
        comercial_name = invoice_id.company_id.partner_id.commercial_name or '-'
        etree.SubElement(party_name, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(comercial_name.strip())
        tag = etree.QName(self._cac, 'PostalAddress')
        address = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'AddressTypeCode')
        etree.SubElement(address, tag.text, nsmap={'cbc': tag.namespace}).text = invoice_id.company_id.district_id.code[
                                                                                 2:]
        tag = etree.QName(self._cac, 'PartyLegalEntity')
        entity = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'RegistrationName')
        #name = invoice_id.company_id.partner_id.legal_name if invoice_id.company_id.partner_id.legal_name.strip() != '-' else invoice_id.company_id.partner_id.name.strip() or '-'
        name = invoice_id.company_id.partner_id.legal_name if invoice_id.company_id.partner_id.legal_name.strip() != '-' else (invoice_id.company_id.partner_id.name.strip() or '-')
        #name = invoice_id.company_id.partner_id.legal_name != '-' and invoice_id.company_id.partner_id.legal_name or invoice_id.company_id.partner_id.name
        etree.SubElement(entity, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(name)

    def _getCompany21(self, invoice_id):
        tag = etree.QName(self._cac, 'AccountingSupplierParty')
        supplier = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'Party')
        party = etree.SubElement(supplier, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'PartyIdentification')
        party_identification = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(party_identification, tag.text, schemeID=invoice_id.company_id.partner_id.doc_type,
                         schemeName='Documento de Identidad', schemeAgencyName='PE:SUNAT',
                         schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06',
                         nsmap={'cbc': tag.namespace}).text = invoice_id.company_id.partner_id.doc_number
        tag = etree.QName(self._cac, 'PartyName')
        party_name = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'Name')
        comercial_name = invoice_id.company_id.partner_id.commercial_name.strip() or invoice_id.company_id.partner_id.name.strip() or '-'
        etree.SubElement(party_name, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(comercial_name)
        tag = etree.QName(self._cac, 'PartyLegalEntity')
        party_legal = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'RegistrationName')
        legal_name = invoice_id.company_id.partner_id.legal_name.strip() if invoice_id.company_id.partner_id.legal_name.strip() != '-' else (invoice_id.company_id.partner_id.name.strip() or '-')
        etree.SubElement(party_legal, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(legal_name)
        tag = etree.QName(self._cac, 'RegistrationAddress')
        address = etree.SubElement(party_legal, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'AddressTypeCode')
        etree.SubElement(address, tag.text, nsmap={'cbc': tag.namespace}).text = '0000'

    def _getDeliveryTerms(self, invoice_id):
        if invoice_id.partner_id.id != invoice_id.partner_shipping_id.id:
            partner_id = invoice_id.partner_shipping_id
        else:
            partner_id = invoice_id.company_id.partner_id
        tag = etree.QName(self._cac, 'Delivery')
        delivery = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'DeliveryLocation')
        location = etree.SubElement(delivery, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'Address')
        address = etree.SubElement(location, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'AddressLine')
        address_line = etree.SubElement(address, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'Line')
        etree.SubElement(address, tag.text, nsmap={'cbc': tag.namespace}).text = partner_id.street[:200]
        tag = etree.QName(self._cbc, 'CitySubdivisionName')
        etree.SubElement(address, tag.text,
                         nsmap={'cbc': tag.namespace}).text = partner_id.street2 and partner_id.street2[:25] or ''
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(address, tag.text, schemeAgencyName='PE:INEI', schemeName='Ubigeos',
                         nsmap={'cbc': tag.namespace}).text = partner_id.district_id.code[2:]
        tag = etree.QName(self._cbc, 'CountrySubentity')
        etree.SubElement(address, tag.text, nsmap={'cbc': tag.namespace}).text = partner_id.state_id.name or '-'
        tag = etree.QName(self._cbc, 'District')
        etree.SubElement(address, tag.text, nsmap={'cbc': tag.namespace}).text = partner_id.district_id.name or '-'
        tag = etree.QName(self._cac, 'Country')
        country = etree.SubElement(address, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'IdentificationCode')
        etree.SubElement(country, tag.text, listID='ISO 3166-1',
                         listAgencyName='United Nations Economic Commission for Europe', listName='Country',
                         nsmap={'cbc': tag.namespace}).text = partner_id.country_id.code or '-'

    def _getPartner(self, invoice_id, line=None):
        tag = etree.QName(self._cac, 'AccountingCustomerParty')
        customer = etree.SubElement(line or self._root, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'CustomerAssignedAccountID')
        partner_id = invoice_id.partner_id.parent_id or invoice_id.partner_id
        etree.SubElement(customer, tag.text, nsmap={
            'cbc': tag.namespace}).text = partner_id.doc_number or partner_id.parent_id.doc_number or ''
        tag = etree.QName(self._cbc, 'AdditionalAccountID')
        etree.SubElement(customer, tag.text, nsmap={
            'cbc': tag.namespace}).text = partner_id.doc_type or partner_id.parent_id.doc_type or '-'
        if not line:
            tag = etree.QName(self._cac, 'Party')
            party = etree.SubElement(customer, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cac, 'PartyLegalEntity')
            entity = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'RegistrationName')
            etree.SubElement(entity, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(partner_id.name or '-')

    def _getPartner21(self, invoice_id, line=None):
        partner_id = invoice_id.partner_id.parent_id or invoice_id.partner_id
        tag = etree.QName(self._cac, 'AccountingCustomerParty')
        customer = etree.SubElement(line or self._root, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'Party')
        party = etree.SubElement(customer, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cac, 'PartyIdentification')
        party_identification = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(party_identification, tag.text, schemeID=partner_id.doc_type or '-',
                         schemeName='Documento de Identidad', schemeAgencyName='PE:SUNAT',
                         schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06',
                         nsmap={'cbc': tag.namespace}).text = partner_id.doc_number or '-'
        tag = etree.QName(self._cac, 'PartyLegalEntity')
        party_legal = etree.SubElement(party, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'RegistrationName')
        legal_name = partner_id.legal_name and partner_id.legal_name.strip() != '-' and partner_id.legal_name.strip() or partner_id.name or '-'
        etree.SubElement(party_legal, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(legal_name)

    def _getDiscrepancyResponse21(self, invoice_id):
        for inv in invoice_id.pe_related_ids:
            tag = etree.QName(self._cac, 'DiscrepancyResponse')
            discrepancy = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ResponseCode')
            if invoice_id.type == 'out_invoice':
                etree.SubElement(discrepancy, tag.text, listAgencyName='PE:SUNAT',
                                 listURI='urn:pe:gob:sunat:cpe:segem:catalogos:catalogo10',
                                 nsmap={'cbc': tag.namespace}).text = invoice_id.pe_debit_note_code
            else:
                if invoice_id.type == 'out_refund':
                    etree.SubElement(discrepancy, tag.text, listAgencyName='PE:SUNAT',
                                     listURI='urn:pe:gob:sunat:cpe:segem:catalogos:catalogo09',
                                     nsmap={'cbc': tag.namespace}).text = invoice_id.pe_credit_note_code
            tag = etree.QName(self._cbc, 'Description')
            etree.SubElement(discrepancy, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(
                invoice_id.name or invoice_id.invoice_line_ids[0].name or '')

    def _getBillingReference(self, invoice_id, line=None):
        for inv in invoice_id.pe_related_ids:
            tag = etree.QName(self._cac, 'BillingReference')
            reference = etree.SubElement(line or self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cac, 'InvoiceDocumentReference')
            invoice = etree.SubElement(reference, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(invoice, tag.text, nsmap={'cbc': tag.namespace}).text = inv.move_name
            tag = etree.QName(self._cbc, 'DocumentTypeCode')
            etree.SubElement(invoice, tag.text, nsmap={'cbc': tag.namespace}).text = inv.pe_invoice_code

    def _getBillingReference21(self, invoice_id, line=None):
        for inv in invoice_id.pe_related_ids:
            tag = etree.QName(self._cac, 'BillingReference')
            reference = etree.SubElement(line or self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cac, 'InvoiceDocumentReference')
            invoice = etree.SubElement(reference, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(invoice, tag.text, nsmap={'cbc': tag.namespace}).text = inv.move_name
            tag = etree.QName(self._cbc, 'DocumentTypeCode')
            etree.SubElement(invoice, tag.text, listAgencyName='PE:SUNAT', listName='Tipo de Documento',
                             listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01',
                             nsmap={'cbc': tag.namespace}).text = inv.pe_invoice_code

    def _getDespatchDocumentReference21(self, invoice_id):
        for despatch_number in invoice_id.env.context.get('despatch_numbers', {}).get(invoice_id.id, []):
            tag = etree.QName(self._cac, 'DespatchDocumentReference')
            reference = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(reference, tag.text, nsmap={'cbc': tag.namespace}).text = despatch_number
            tag = etree.QName(self._cbc, 'DocumentTypeCode')
            etree.SubElement(reference, tag.text, listName='Tipo de Documento',
                             listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01',
                             nsmap={'cbc': tag.namespace}).text = '09'

    def _getPrepaidPayment(self, invoice_id):
        for line in invoice_id.invoice_line_ids.mapped('sale_line_ids').mapped('order_id').mapped(
                'invoice_ids').filtered(lambda inv: inv.pe_sunat_transaction in ('04',) and inv.pe_invoice_code in (
        '01', '03') and inv.id != invoice_id.id and inv.state not in ('draft',
                                                                      'cancel')):
            tag = etree.QName(self._cac, 'PrepaidPayment')
            prepaid = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            if line.pe_invoice_code == '01':
                etree.SubElement(prepaid, tag.text, schemeID='02', nsmap={'cbc': tag.namespace}).text = line.move_name
            else:
                if line.pe_invoice_code == '03':
                    etree.SubElement(prepaid, tag.text, schemeID='03',
                                     nsmap={'cbc': tag.namespace}).text = line.move_name
            tag = etree.QName(self._cbc, 'PaidAmount')
            etree.SubElement(prepaid, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(line.amount_total, 2))
            tag = etree.QName(self._cbc, 'InstructionID')
            etree.SubElement(prepaid, tag.text, schemeID=invoice_id.partner_id.doc_type or '-',
                             nsmap={'cbc': tag.namespace}).text = line.partner_id.doc_number or '-'

    def _getPrepaidPayment21(self, invoice_id):
        for line in invoice_id.invoice_line_ids.mapped('sale_line_ids').mapped('order_id').mapped(
                'invoice_ids').filtered(lambda inv: inv.pe_sunat_transaction in ('04',) and inv.pe_invoice_code in (
        '01', '03') and inv.id != invoice_id.id and nv.state not in ('draft',
                                                                     'cancel')):
            tag = etree.QName(self._cac, 'PrepaidPayment')
            prepaid = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            if line.pe_invoice_code == '01':
                etree.SubElement(prepaid, tag.text, schemeID='02',
                                 schemeName='SUNAT:Identificador de Documentos Relacionados',
                                 schemeAgencyName='PE:SUNAT', nsmap={'cbc': tag.namespace}).text = line.move_name
            else:
                if line.pe_invoice_code == '03':
                    etree.SubElement(prepaid, tag.text, schemeID='03',
                                     schemeName='SUNAT:Identificador de Documentos Relacionados',
                                     schemeAgencyName='PE:SUNAT', nsmap={'cbc': tag.namespace}).text = line.move_name
            tag = etree.QName(self._cbc, 'PaidAmount')
            etree.SubElement(prepaid, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(line.amount_total, 2))
            tag = etree.QName(self._cbc, 'InstructionID')
            etree.SubElement(prepaid, tag.text, schemeID=invoice_id.partner_id.doc_type or '-',
                             nsmap={'cbc': tag.namespace}).text = line.partner_id.doc_number or '-'

    def _getTaxTotal(self, invoice_id):
        amount_tax = invoice_id.currency_id.round(
            invoice_id.pe_amount_tax * (1 - (invoice_id.discount_rate or 0.0) / 100))
        for tax in invoice_id.tax_line_ids.filtered(
                lambda tax: tax.tax_id.pe_tax_type.code in ('1000', '2000', '9999')):
            tag = etree.QName(self._cac, 'TaxTotal')
            total = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'TaxAmount')
            etree.SubElement(total, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(tax.amount, 2))
            tag = etree.QName(self._cac, 'TaxSubtotal')
            tax_subtotal = etree.SubElement(total, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'TaxAmount')
            amount_tax_line = invoice_id.currency_id.round(tax.amount * (1 - (invoice_id.discount_rate or 0.0) / 100))
            etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(amount_tax_line, 2))
            tag = etree.QName(self._cac, 'TaxCategory')
            category = etree.SubElement(tax_subtotal, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cac, 'TaxScheme')
            scheme = etree.SubElement(category, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = tax.tax_id.pe_tax_type.code
            tag = etree.QName(self._cbc, 'Name')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = tax.tax_id.pe_tax_type.name
            tag = etree.QName(self._cbc, 'TaxTypeCode')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = tax.tax_id.pe_tax_type.un_ece_code


        if not invoice_id.tax_line_ids.filtered(lambda tax: tax.tax_id.pe_tax_type.code == '1000'):
            tag = etree.QName(self._cac, 'TaxTotal')
            total = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'TaxAmount')
            etree.SubElement(total, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(0.0)
            tag = etree.QName(self._cac, 'TaxSubtotal')
            tax_subtotal = etree.SubElement(total, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'TaxAmount')
            etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(0.0)
            tag = etree.QName(self._cac, 'TaxCategory')
            category = etree.SubElement(tax_subtotal, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cac, 'TaxScheme')
            scheme = etree.SubElement(category, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = '1000'
            tag = etree.QName(self._cbc, 'Name')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = 'IGV'

    def _getTaxTotal21(self, invoice_id):
        tag = etree.QName(self._cac, 'TaxTotal')
        total = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
        tag = etree.QName(self._cbc, 'TaxAmount')
        amount_tax = invoice_id.pe_amount_tax
        etree.SubElement(total, tag.text, currencyID=invoice_id.currency_id.name,
                         nsmap={'cbc': tag.namespace}).text = str(round(amount_tax, 2))

        for tax in invoice_id.tax_line_ids.filtered(lambda tax: tax.tax_id.pe_tax_type.code != '9996'):
            tag = etree.QName(self._cac, 'TaxSubtotal')
            tax_subtotal = etree.SubElement(total, tag.text, nsmap={'cac': tag.namespace})
            if tax.tax_id.pe_tax_type.code != '7152':
                tag = etree.QName(self._cbc, 'TaxableAmount')
                base_tax_line = tax.base
                if tax.tax_id.pe_tax_type.code == '9996':
                    etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                                     nsmap={'cbc': tag.namespace}).text = str(round(invoice_id.pe_free_amount, 2))
                else:
                    etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                                     nsmap={'cbc': tag.namespace}).text = str(round(base_tax_line, 2))

            tag = etree.QName(self._cbc, 'TaxAmount')
            amount_tax_line = tax.amount
            if tax.tax_id.pe_tax_type.code == '9996':
                etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = '0.0'
            else:
                etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(round(amount_tax_line, 2))
            tag = etree.QName(self._cac, 'TaxCategory')
            category = etree.SubElement(tax_subtotal, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cac, 'TaxScheme')
            scheme = etree.SubElement(category, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(scheme, tag.text, schemeName='Codigo de tributos', schemeAgencyName='PE:SUNAT',
                             schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo05',
                             nsmap={'cbc': tag.namespace}).text = tax.tax_id.pe_tax_type.code
            tag = etree.QName(self._cbc, 'Name')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = tax.tax_id.pe_tax_type.name
            tag = etree.QName(self._cbc, 'TaxTypeCode')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = tax.tax_id.pe_tax_type.un_ece_code
        line_ids = invoice_id.invoice_line_ids.filtered(
            lambda ln: ln.pe_affectation_code not in ('10', '20', '30', '40'))
        tax_ids = line_ids.mapped('invoice_line_tax_ids')
        for tax in tax_ids.filtered(lambda tax: tax.pe_tax_type.code != '9996'):
            base_amount = 0.0
            tax_amount = 0.0
            for line in line_ids:
                price_unit = line.price_unit
                if tax.id in line.invoice_line_tax_ids.ids:
                    tax_values = tax.with_context(round=False).compute_all(price_unit, currency=invoice_id.currency_id,
                                                                           quantity=line.quantity,
                                                                           product=line.product_id,
                                                                           partner=invoice_id.partner_id)
                    base_amount += invoice_id.currency_id.round(tax_values['total_excluded'])
                    tax_amount += invoice_id.currency_id.round(tax_values['taxes'][0]['amount'])

            tag = etree.QName(self._cac, 'TaxSubtotal')
            tax_subtotal = etree.SubElement(total, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'TaxableAmount')
            etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(base_amount, 2))
            tag = etree.QName(self._cbc, 'TaxAmount')
            amount_tax_line = tax.amount
            etree.SubElement(tax_subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(tax_amount, 2))
            tag = etree.QName(self._cac, 'TaxCategory')
            category = etree.SubElement(tax_subtotal, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cac, 'TaxScheme')
            scheme = etree.SubElement(category, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(scheme, tag.text, schemeName='Codigo de tributos', schemeAgencyName='PE:SUNAT',
                             schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo05',
                             nsmap={'cbc': tag.namespace}).text = '9996'
            tag = etree.QName(self._cbc, 'Name')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = 'GRA'
            tag = etree.QName(self._cbc, 'TaxTypeCode')
            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = 'FRE'

        return amount_tax

    def _getLegalMonetaryTotal21(self, invoice_id):
        if invoice_id.journal_id.pe_invoice_code == '08':
            tag = etree.QName(self._cac, 'RequestedMonetaryTotal')
        else:
            tag = etree.QName(self._cac, 'LegalMonetaryTotal')
        total = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
        prepaid_amount = 0
        for line in invoice_id.invoice_line_ids.mapped('sale_line_ids').mapped('order_id').mapped(
                'invoice_ids').filtered(lambda inv: inv.pe_sunat_transaction in ('04',) and inv.pe_invoice_code in (
        '01', '03') and inv.id != invoice_id.id):
            amount = line.currency_id.with_context(date=invoice_id.date_invoice).compute(line.amount_total,
                                                                                         invoice_id.currency_id)
            prepaid_amount += amount

        other = 0.0
        for tax in invoice_id.tax_line_ids.filtered(lambda t: t.tax_id.pe_tax_type.code == '9999'):
            other += invoice_id.currency_id.round(tax.base * (1 - (invoice_id.discount_rate or 0.0) / 100))

        tag = etree.QName(self._cbc, 'ChargeTotalAmount')
        etree.SubElement(total, tag.text, currencyID=invoice_id.currency_id.name,
                         nsmap={'cbc': tag.namespace}).text = str(round(other, 2))
        tag = etree.QName(self._cbc, 'PayableAmount')
        amount_total = invoice_id.amount_total
        etree.SubElement(total, tag.text, currencyID=invoice_id.currency_id.name,
                         nsmap={'cbc': tag.namespace}).text = str(round(amount_total, 2))

    def _getAllowanceCharge(self, invoice_id):
        if invoice_id.pe_total_discount > 0.0:
            tag = etree.QName(self._cac, 'AllowanceCharge')
            allowance_charge = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ChargeIndicator')
            etree.SubElement(allowance_charge, tag.text, nsmap={'cbc': tag.namespace}).text = 'false'
            tag = etree.QName(self._cbc, 'AllowanceChargeReasonCode')
            etree.SubElement(allowance_charge, tag.text, listAgencyName='PE:SUNAT', listName='Cargo/descuento',
                             listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo53',
                             nsmap={'cbc': tag.namespace}).text = '02'
            tag = etree.QName(self._cbc, 'MultiplierFactorNumeric')
            etree.SubElement(allowance_charge, tag.text, nsmap={'cbc': tag.namespace}).text = str(round(
                (invoice_id.pe_total_discount - invoice_id.pe_total_discount_tax) / (invoice_id.amount_untaxed + (
                            invoice_id.pe_total_discount - invoice_id.pe_total_discount_tax)), 5))
            tag = etree.QName(self._cbc, 'Amount')
            etree.SubElement(allowance_charge, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(
                round(invoice_id.pe_total_discount - invoice_id.pe_total_discount_tax, 2))
            tag = etree.QName(self._cbc, 'BaseAmount')
            amount_total = invoice_id.amount_untaxed + (invoice_id.pe_total_discount - invoice_id.pe_total_discount_tax)
            etree.SubElement(allowance_charge, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(amount_total, 2))

    def _getDocumentLines21(self, invoice_id):
        cont = 1
        decimal_precision_obj = invoice_id.env['decimal.precision']
        digits = decimal_precision_obj.precision_get('Product Price') or 2
        for line in invoice_id.invoice_line_ids.filtered(lambda ln: ln.price_subtotal >= 0):
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.invoice_line_tax_ids.with_context(round=False).compute_all(price_unit,
                                                                                    currency=invoice_id.currency_id,
                                                                                    quantity=line.quantity,
                                                                                    product=line.product_id,
                                                                                    partner=invoice_id.partner_id)
            tax_total_amount = taxes.get('total_included', 0.0) - taxes.get('total_excluded', 0.0)
            if invoice_id.pe_invoice_code == '08':
                tag = etree.QName(self._cac, 'DebitNoteLine')
            elif invoice_id.pe_invoice_code == '07':
                tag = etree.QName(self._cac, 'CreditNoteLine')
            else:
                tag = etree.QName(self._cac, 'InvoiceLine')

            inv_line = etree.SubElement(self._root, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'ID')
            etree.SubElement(inv_line, tag.text, nsmap={'cbc': tag.namespace}).text = str(cont)
            cont += 1

            if invoice_id.pe_invoice_code == '08':
                tag = etree.QName(self._cbc, 'DebitedQuantity')
            elif invoice_id.pe_invoice_code == '07':
                tag = etree.QName(self._cbc, 'CreditedQuantity')
            else:
                tag = etree.QName(self._cbc, 'InvoicedQuantity')

            etree.SubElement(inv_line, tag.text, unitCode=line.uom_id and line.uom_id.sunat_code or 'NIU',
                             unitCodeListID='UN/ECE rec 20',
                             unitCodeListAgencyName='United Nations Economic Commission for Europe',
                             nsmap={'cbc': tag.namespace}).text = str(line.quantity)
            tag = etree.QName(self._cbc, 'LineExtensionAmount')
            etree.SubElement(inv_line, tag.text, currencyID=invoice_id.currency_id.name,
                             nsmap={'cbc': tag.namespace}).text = str(round(line.price_subtotal, 2))
            tag = etree.QName(self._cac, 'PricingReference')
            pricing = etree.SubElement(inv_line, tag.text, nsmap={'cac': tag.namespace})
            price_unit_all = line.get_price_unit(True)['total_included']

            if price_unit_all > 0:
                tag = etree.QName(self._cac, 'AlternativeConditionPrice')
                alternative = etree.SubElement(pricing, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'PriceAmount')
            if price_unit_all == 0 or invoice_id.pe_invoice_code in ('07', '08'):
                etree.SubElement(alternative, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(
                    round(float_round(price_unit_all, digits), 10))
            else:
                etree.SubElement(alternative, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(
                    round(float_round(line.get_price_unit()['total_included'], digits), 10))
            tag = etree.QName(self._cbc, 'PriceTypeCode')
            etree.SubElement(alternative, tag.text, listName='Tipo de Precio', listAgencyName='PE:SUNAT',
                             listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16',
                             nsmap={'cbc': tag.namespace}).text = '01'

            if price_unit_all == 0.0:
                tag = etree.QName(self._cac, 'AlternativeConditionPrice')
                alternative = etree.SubElement(pricing, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'PriceAmount')
                etree.SubElement(alternative, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(
                    round(float_round(line.get_price_unit()['total_included'], digits), 10))
                tag = etree.QName(self._cbc, 'PriceTypeCode')
                etree.SubElement(alternative, tag.text, listName='Tipo de Precio', listAgencyName='PE:SUNAT',
                                 listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16',
                                 nsmap={'cbc': tag.namespace}).text = '02'

            if line.discount > 0 and line.discount < 100 and invoice_id.pe_invoice_code not in ('07', '08'):
                tag = etree.QName(self._cac, 'AllowanceCharge')
                charge = etree.SubElement(inv_line, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'ChargeIndicator')
                etree.SubElement(charge, tag.text, nsmap={'cbc': tag.namespace}).text = 'false'
                tag = etree.QName(self._cbc, 'AllowanceChargeReasonCode')
                etree.SubElement(charge, tag.text, nsmap={'cbc': tag.namespace}).text = '00'
                tag = etree.QName(self._cbc, 'MultiplierFactorNumeric')
                etree.SubElement(charge, tag.text, nsmap={'cbc': tag.namespace}).text = str(
                    round(line.discount / 100, 5))
                tag = etree.QName(self._cbc, 'Amount')
                etree.SubElement(charge, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(
                    round(float_round(line.discount == 100 and 0.0 or line.amount_discount, digits), 10))
                tag = etree.QName(self._cbc, 'BaseAmount')
                etree.SubElement(charge, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(
                    round(float_round(line.price_subtotal + line.amount_discount, digits), 10))

            tag = etree.QName(self._cac, 'TaxTotal')
            total = etree.SubElement(inv_line, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'TaxAmount')
            tax_total_amount = taxes.get('total_included', 0.0) - taxes.get('total_excluded', 0.0)
            digits_rounding_precision = invoice_id.currency_id.rounding

            if line.invoice_line_tax_ids.filtered(lambda tax: tax.pe_tax_type.code == '9996'):
                tax_total_values = line.invoice_line_tax_ids.with_context(round=False).filtered(
                    lambda tax: tax.pe_tax_type.code != '9996').compute_all(line.price_unit,
                                                                            currency=invoice_id.currency_id,
                                                                            quantity=line.quantity,
                                                                            product=line.product_id,
                                                                            partner=invoice_id.partner_id)
                etree.SubElement(total, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(round(float_round(
                    tax_total_values.get('total_included', 0.0) - tax_total_values.get('total_excluded', 0.0),
                    precision_rounding=digits_rounding_precision), 2))
            else:
                etree.SubElement(total, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(
                    round(float_round(tax_total_amount, precision_rounding=digits_rounding_precision), 2))
            for tax in line.invoice_line_tax_ids:
                if tax.pe_tax_type.code == '9996':
                    price_unit = line.price_unit
                    tax_values = tax_total_values
                else:
                    if line.discount == 100:
                        continue
                    else:
                        tax_values = tax.with_context(round=False).compute_all(price_unit,
                                                                               currency=invoice_id.currency_id,
                                                                               quantity=line.quantity,
                                                                               product=line.product_id,
                                                                               partner=invoice_id.partner_id)
                    if float_is_zero(tax_values['total_excluded'],
                                     precision_rounding=digits_rounding_precision) and tax.pe_tax_type.code == '9996' or not float_is_zero(
                            tax_values['total_excluded'], precision_rounding=digits_rounding_precision):
                        tag = etree.QName(self._cac, 'TaxSubtotal')
                        subtotal = etree.SubElement(total, tag.text, nsmap={'cac': tag.namespace})

                        if tax.pe_tax_type.code != '7152':
                            tag = etree.QName(self._cbc, 'TaxableAmount')
                            etree.SubElement(subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                                             nsmap={'cbc': tag.namespace}).text = str(round(
                                float_round(tax_values['total_excluded'], precision_rounding=digits_rounding_precision), 2))
                        tag = etree.QName(self._cbc, 'TaxAmount')
                        etree.SubElement(subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                                         nsmap={'cbc': tag.namespace}).text = str(round(
                            float_round(tax_values['taxes'][0]['amount'], precision_rounding=digits_rounding_precision),
                            2))
                        if tax.pe_tax_type.code == '7152':
                            base_unit_7152 = tax_values['taxes'][0]['amount'] / tax.amount
                            tag = etree.QName(self._cbc, 'BaseUnitMeasure')
                            etree.SubElement(subtotal, tag.text, unitCode='NIU',
                                             nsmap={'cbc': tag.namespace}).text = str( "{:.{}f}".format(base_unit_7152, 0))
                            tag = etree.QName(self._cbc, 'PerUnitAmount')
                            etree.SubElement(subtotal, tag.text, currencyID=invoice_id.currency_id.name,
                                             nsmap={'cbc': tag.namespace}).text = str(round(tax.amount, 2))
                        tag = etree.QName(self._cac, 'TaxCategory')
                        category = etree.SubElement(subtotal, tag.text, nsmap={'cac': tag.namespace})
                        if tax.pe_tax_type.code != '7152':
                            tag = etree.QName(self._cbc, 'Percent')
                            taxes_ids = line.invoice_line_tax_ids.filtered(lambda tax: tax.pe_tax_type.code != '9996')
                            amount = tax.pe_tax_type.code == '9996' and (
                                        len(taxes_ids) > 1 and taxes_ids[0].amount or taxes_ids.amount) or tax.amount
                            etree.SubElement(category, tag.text, nsmap={'cbc': tag.namespace}).text = str(amount)
                        if tax.pe_tax_type.code == '2000':
                            tag = etree.QName(self._cbc, 'TierRange')
                            etree.SubElement(category, tag.text, nsmap={
                                'cbc': tag.namespace}).text = line.pe_tier_range or tax.pe_tier_range
                        else:
                            if tax.pe_tax_type.code != '7152':
                                tag = etree.QName(self._cbc, 'TaxExemptionReasonCode')
                                etree.SubElement(category, tag.text, listAgencyName='PE:SUNAT',
                                                 listName='Afectacion del IGV',
                                                 listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07',
                                                 nsmap={'cbc': tag.namespace}).text = line.pe_affectation_code
                        tag = etree.QName(self._cac, 'TaxScheme')
                        scheme = etree.SubElement(category, tag.text, nsmap={'cac': tag.namespace})
                        tag = etree.QName(self._cbc, 'ID')
                        etree.SubElement(scheme, tag.text, schemeName='Codigo de tributos', schemeAgencyName='PE:SUNAT',
                                         schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo05',
                                         nsmap={'cbc': tag.namespace}).text = tax.pe_tax_type.code
                        tag = etree.QName(self._cbc, 'Name')
                        etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = tax.pe_tax_type.name
                        tag = etree.QName(self._cbc, 'TaxTypeCode')
                        etree.SubElement(scheme, tag.text,
                                         nsmap={'cbc': tag.namespace}).text = tax.pe_tax_type.un_ece_code

            tag = etree.QName(self._cac, 'Item')
            item = etree.SubElement(inv_line, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'Description')
            product_name = line.name.replace('\n', ' ')[:250]
            etree.SubElement(item, tag.text, nsmap={'cbc': tag.namespace}).text = etree.CDATA(product_name)

            if line.product_id.default_code:
                tag = etree.QName(self._cac, 'SellersItemIdentification')
                identification = etree.SubElement(item, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'ID')
                etree.SubElement(identification, tag.text, nsmap={
                    'cbc': tag.namespace}).text = line.product_id and line.product_id.default_code or ''
            if line.pe_license_plate or invoice_id.pe_license_plate and line.product_id.require_plate:
                tag = etree.QName(self._cac, 'AdditionalItemProperty')
                identification = etree.SubElement(item, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'Name')
                etree.SubElement(identification, tag.text,
                                 nsmap={'cbc': tag.namespace}).text = 'Gastos Art. 37 Renta: Número de Placa'
                tag = etree.QName(self._cbc, 'NameCode')
                etree.SubElement(identification, tag.text, listName='Propiedad del item', listAgencyName='PE:SUNAT',
                                 listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo55',
                                 nsmap={'cbc': tag.namespace}).text = '7000'
                tag = etree.QName(self._cbc, 'Value')
                etree.SubElement(identification, tag.text, nsmap={
                    'cbc': tag.namespace}).text = line.pe_license_plate or invoice_id.pe_license_plate or ''

            tag = etree.QName(self._cac, 'Price')
            price = etree.SubElement(inv_line, tag.text, nsmap={'cac': tag.namespace})
            tag = etree.QName(self._cbc, 'PriceAmount')
            if price_unit_all == 0.0:
                etree.SubElement(price, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(round(price_unit_all, 10))
            else:
                etree.SubElement(price, tag.text, currencyID=invoice_id.currency_id.name,
                                 nsmap={'cbc': tag.namespace}).text = str(
                    round(float_round(line.get_price_unit()['total_excluded'], digits), 10))

    def getInvoice(self, invoice_id):
        xmlns = etree.QName('urn:oasis:names:specification:ubl:schema:xsd:Invoice-2', 'Invoice')
        nsmap1 = OrderedDict([(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc), ('ccts', self._ccts),
                              (
                                  'ds', self._ds), ('ext', self._ext), ('qdt', self._qdt), ('sac', self._sac),
                              ('udt', self._udt),
                              (
                                  'xsi', self._xsi)])
        self._root = etree.Element(xmlns.text, nsmap=nsmap1)
        tag = etree.QName(self._ext, 'UBLExtensions')
        extensions = etree.SubElement(self._root, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'UBLExtension')
        extension = etree.SubElement(extensions, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'ExtensionContent')
        content = etree.SubElement(extension, tag.text, nsmap={'ext': tag.namespace})
        self._getX509Template(content)
        self._getUBLVersion21()
        self._getDocumentDetail21(invoice_id)
        self._getSignature(invoice_id)
        self._getCompany21(invoice_id)
        self._getPartner21(invoice_id)
        self._getPrepaidPayment21(invoice_id)
        self._getAllowanceCharge(invoice_id)
        amount_tax = self._getTaxTotal21(invoice_id)
        self._getLegalMonetaryTotal21(invoice_id)
        self._getDocumentLines21(invoice_id)
        xml_str = etree.tostring(self._root, pretty_print=True, xml_declaration=True, encoding='utf-8',
                                 standalone=False)
        return xml_str

    def getCreditNote(self, invoice_id):
        xmlns = etree.QName('urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2', 'CreditNote')
        nsmap1 = OrderedDict([(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc), ('ccts', self._ccts),
                              (
                                  'ds', self._ds), ('ext', self._ext), ('qdt', self._qdt), ('sac', self._sac),
                              ('udt', self._udt),
                              (
                                  'xsi', self._xsi)])
        self._root = etree.Element(xmlns.text, nsmap=nsmap1)
        tag = etree.QName(self._ext, 'UBLExtensions')
        extensions = etree.SubElement(self._root, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'UBLExtension')
        extension = etree.SubElement(extensions, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'ExtensionContent')
        content = etree.SubElement(extension, tag.text, nsmap={'ext': tag.namespace})
        self._getX509Template(content)
        self._getUBLVersion21()
        self._getDocumentDetail21(invoice_id)
        self._getDiscrepancyResponse21(invoice_id)
        self._getBillingReference21(invoice_id)
        self._getDespatchDocumentReference21(invoice_id)
        self._getSignature(invoice_id)
        self._getCompany21(invoice_id)
        self._getPartner21(invoice_id)
        self._getAllowanceCharge(invoice_id)
        amount_tax = self._getTaxTotal21(invoice_id)
        self._getLegalMonetaryTotal21(invoice_id)
        self._getDocumentLines21(invoice_id)
        xml_str = etree.tostring(self._root, pretty_print=True, xml_declaration=True, encoding='utf-8',
                                 standalone=False)
        return xml_str

    def getDebitNote(self, invoice_id):
        xmlns = etree.QName('urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2', 'DebitNote')
        nsmap1 = OrderedDict([(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc), ('ccts', self._ccts),
                              (
                                  'ds', self._ds), ('ext', self._ext), ('qdt', self._qdt), ('sac', self._sac),
                              ('udt', self._udt),
                              (
                                  'xsi', self._xsi)])
        self._root = etree.Element(xmlns.text, nsmap=nsmap1)
        tag = etree.QName(self._ext, 'UBLExtensions')
        extensions = etree.SubElement(self._root, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'UBLExtension')
        extension = etree.SubElement(extensions, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'ExtensionContent')
        content = etree.SubElement(extension, tag.text, nsmap={'ext': tag.namespace})
        self._getX509Template(content)
        self._getUBLVersion21()
        self._getDocumentDetail21(invoice_id)
        self._getDiscrepancyResponse21(invoice_id)
        self._getBillingReference21(invoice_id)
        self._getDespatchDocumentReference21(invoice_id)
        self._getSignature(invoice_id)
        self._getCompany21(invoice_id)
        self._getPartner21(invoice_id)
        amount_tax = self._getTaxTotal21(invoice_id)
        self._getLegalMonetaryTotal21(invoice_id)
        self._getDocumentLines21(invoice_id)
        xml_str = etree.tostring(self._root, pretty_print=True, xml_declaration=True, encoding='utf-8',
                                 standalone=False)
        return xml_str

    def getVoidedDocuments(self, batch):
        xmlns = etree.QName('urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1', 'VoidedDocuments')
        nsmap1 = OrderedDict([(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc), ('ccts', self._ccts),
                              (
                                  'ds', self._ds), ('ext', self._ext), ('qdt', self._qdt), ('sac', self._sac),
                              ('udt', self._udt),
                              (
                                  'xsi', self._xsi)])
        self._root = etree.Element(xmlns.text, nsmap=nsmap1)
        tag = etree.QName(self._ext, 'UBLExtensions')
        extensions = etree.SubElement(self._root, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'UBLExtension')
        extension = etree.SubElement(extensions, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'ExtensionContent')
        content = etree.SubElement(extension, tag.text, nsmap={'ext': tag.namespace})
        self._getX509Template(content)
        self._getUBLVersion(version='2.0', customization='1.0')
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = batch.name
        tag = etree.QName(self._cbc, 'ReferenceDate')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = datetime.strptime(batch.date.strftime('%Y-%m-%d'),'%Y-%m-%d').date().strftime('%Y-%m-%d') #batch.date
        tag = etree.QName(self._cbc, 'IssueDate')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = datetime.strptime(batch.send_date.strftime('%Y-%m-%d %H:%M:%S'),'%Y-%m-%d %H:%M:%S').date().strftime('%Y-%m-%d')
        self._getSignature(batch)
        self._getCompany(batch)
        cont = 1
        for invoice_id in batch.voided_ids:
            if invoice_id.pe_cpe_id.state in ('draft', 'generate', 'cancel'):
                raise UserError(
                    _('The invoice N° %s must be sent to the sunat to generate this document.') % invoice_id.move_name)
            tag = etree.QName(self._sac, 'VoidedDocumentsLine')
            line = etree.SubElement(self._root, tag.text, nsmap={'sac': tag.namespace})
            tag = etree.QName(self._cbc, 'LineID')
            etree.SubElement(line, tag.text, nsmap={'cbc': tag.namespace}).text = str(cont)
            cont += 1
            tag = etree.QName(self._cbc, 'DocumentTypeCode')
            etree.SubElement(line, tag.text, nsmap={'cbc': tag.namespace}).text = invoice_id.journal_id.pe_invoice_code
            tag = etree.QName(self._sac, 'DocumentSerialID')
            etree.SubElement(line, tag.text, nsmap={'sac': tag.namespace}).text = invoice_id.move_name and \
                                                                                  invoice_id.move_name.split('-')[0]
            tag = etree.QName(self._sac, 'DocumentNumberID')
            etree.SubElement(line, tag.text, nsmap={'sac': tag.namespace}).text = invoice_id.move_name and \
                                                                                  invoice_id.move_name.split('-')[1]
            tag = etree.QName(self._sac, 'VoidReasonDescription')
            etree.SubElement(line, tag.text, nsmap={'sac': tag.namespace}).text = invoice_id.state in ('cancel',
                                                                                                       'annul') and 'Anulado'

        xml_str = etree.tostring(self._root, pretty_print=True, xml_declaration=True, encoding='utf-8',
                                 standalone=False)
        return xml_str

    def getSummaryDocuments(self, batch):
        journal_ids = batch.summary_ids.mapped('journal_id')
        xmlns = etree.QName('urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1', 'SummaryDocuments')
        nsmap1 = OrderedDict([(None, xmlns.namespace), ('cac', self._cac), ('cbc', self._cbc), ('ds', self._ds),
                              (
                                  'ext', self._ext), ('sac', self._sac), ('xsi', self._xsi)])
        self._root = etree.Element(xmlns.text, nsmap=nsmap1)
        tag = etree.QName(self._ext, 'UBLExtensions')
        extensions = etree.SubElement(self._root, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'UBLExtension')
        extension = etree.SubElement(extensions, tag.text, nsmap={'ext': tag.namespace})
        tag = etree.QName(self._ext, 'ExtensionContent')
        content = etree.SubElement(extension, tag.text, nsmap={'ext': tag.namespace})
        self._getX509Template(content)
        self._getUBLVersion(version='2.0', customization='1.1')
        tag = etree.QName(self._cbc, 'ID')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = batch.name
        tag = etree.QName(self._cbc, 'ReferenceDate')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = datetime.strptime(batch.date.strftime('%Y-%m-%d'),'%Y-%m-%d').date().strftime('%Y-%m-%d') #batch.date
        tag = etree.QName(self._cbc, 'IssueDate')
        etree.SubElement(self._root, tag.text, nsmap={'cbc': tag.namespace}).text = datetime.strptime(batch.send_date.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S').date().strftime('%Y-%m-%d')
        self._getSignature(batch)
        self._getCompany(batch)
        cont = 1
        for journal_id in journal_ids:
            summary_total = 0
            summary_untaxed = 0
            summary_inaffected = 0
            summary_exonerated = 0
            summary_gift = 0
            summary_export = 0
            for invoice_id in batch.summary_ids.filtered(lambda inv: inv.journal_id.id == journal_id.id).sorted(
                    key=lambda r: r.move_name):
                if invoice_id.pe_cpe_id.state in ('draft', 'cancel'):
                    raise UserError(_(
                        'The invoice N° %s must be sent to the sunat to generate this document.') % invoice_id.move_name)
                taxes = []
                taxes.append({'amount_tax_line': 0, 'tax_name': '1000', 'tax_description': 'IGV', 'tax_type_pe': 'VAT'})
                taxes.append({'amount_tax_line': 0, 'tax_name': '2000', 'tax_description': 'ISC', 'tax_type_pe': 'EXC'})
                taxes.append({'amount_tax_line': 0, 'tax_name': '9999', 'tax_description': 'OTR', 'tax_type_pe': 'OTH'})
                total = invoice_id.amount_total
                summary_allowcharge = invoice_id.pe_total_discount - invoice_id.pe_total_discount_tax
                for tax in invoice_id.tax_line_ids.filtered(
                        lambda tax: tax.tax_id.pe_tax_type.code in ('1000', '2000', '9999')):
                    amount_tax_line = tax.amount
                    for i in range(len(taxes)):
                        if taxes[i]['tax_name'] == tax.tax_id.pe_tax_type.code:
                            taxes[i]['amount_tax_line'] += amount_tax_line

                currency_code = invoice_id.currency_id.name
                tag = etree.QName(self._sac, 'SummaryDocumentsLine')
                line = etree.SubElement(self._root, tag.text, nsmap={'sac': tag.namespace})
                tag = etree.QName(self._cbc, 'LineID')
                etree.SubElement(line, tag.text, nsmap={'cbc': tag.namespace}).text = str(cont)
                cont += 1
                tag = etree.QName(self._cbc, 'DocumentTypeCode')
                etree.SubElement(line, tag.text, nsmap={'cbc': tag.namespace}).text = journal_id.pe_invoice_code
                tag = etree.QName(self._cbc, 'ID')
                etree.SubElement(line, tag.text, nsmap={'cbc': tag.namespace}).text = invoice_id.move_name
                self._getPartner(invoice_id, line)
                if journal_id.pe_invoice_code in ('07', '08'):
                    self._getBillingReference(invoice_id, line)
                tag = etree.QName(self._cac, 'Status')
                status = etree.SubElement(line, tag.text, nsmap={'cac': tag.namespace})
                tag = etree.QName(self._cbc, 'ConditionCode')
                if invoice_id.pe_cpe_id.state == 'done':
                    etree.SubElement(status, tag.text, nsmap={'cbc': tag.namespace}).text = invoice_id.pe_condition_code
                else:
                    etree.SubElement(status, tag.text, nsmap={'cbc': tag.namespace}).text = '1'
                tag = etree.QName(self._sac, 'TotalAmount')
                etree.SubElement(line, tag.text, currencyID=currency_code, nsmap={'sac': tag.namespace}).text = str(
                    round(total, 2))
                if invoice_id.pe_taxable_amount > 0:
                    tag = etree.QName(self._sac, 'BillingPayment')
                    billing = etree.SubElement(line, tag.text, nsmap={'sac': tag.namespace})
                    tag = etree.QName(self._cbc, 'PaidAmount')
                    etree.SubElement(billing, tag.text, currencyID=currency_code,
                                     nsmap={'cbc': tag.namespace}).text = str(round(invoice_id.pe_taxable_amount, 2))
                    tag = etree.QName(self._cbc, 'InstructionID')
                    etree.SubElement(billing, tag.text, nsmap={'cbc': tag.namespace}).text = '01'
                if invoice_id.pe_exonerated_amount > 0:
                    tag = etree.QName(self._sac, 'BillingPayment')
                    billing = etree.SubElement(line, tag.text, nsmap={'sac': tag.namespace})
                    tag = etree.QName(self._cbc, 'PaidAmount')
                    etree.SubElement(billing, tag.text, currencyID=currency_code,
                                     nsmap={'cbc': tag.namespace}).text = str(round(invoice_id.pe_exonerated_amount, 2))
                    tag = etree.QName(self._cbc, 'InstructionID')
                    etree.SubElement(billing, tag.text, nsmap={'cbc': tag.namespace}).text = '02'
                if invoice_id.pe_unaffected_amount > 0:
                    tag = etree.QName(self._sac, 'BillingPayment')
                    billing = etree.SubElement(line, tag.text, nsmap={'sac': tag.namespace})
                    tag = etree.QName(self._cbc, 'PaidAmount')
                    etree.SubElement(billing, tag.text, currencyID=currency_code,
                                     nsmap={'cbc': tag.namespace}).text = str(round(invoice_id.pe_unaffected_amount, 2))
                    tag = etree.QName(self._cbc, 'InstructionID')
                    etree.SubElement(billing, tag.text, nsmap={'cbc': tag.namespace}).text = '03'
                if invoice_id.pe_free_amount > 0:
                    tag = etree.QName(self._sac, 'BillingPayment')
                    billing = etree.SubElement(line, tag.text, nsmap={'sac': tag.namespace})
                    tag = etree.QName(self._cbc, 'PaidAmount')
                    etree.SubElement(billing, tag.text, currencyID=currency_code,
                                     nsmap={'cbc': tag.namespace}).text = str(round(invoice_id.pe_free_amount, 2))
                    tag = etree.QName(self._cbc, 'InstructionID')
                    etree.SubElement(billing, tag.text, nsmap={'cbc': tag.namespace}).text = '05'
                if summary_allowcharge > 0:
                    tag = etree.QName(self._cac, 'AllowanceCharge')
                    allowance = etree.SubElement(line, tag.text, nsmap={'cac': tag.namespace})
                    tag = etree.QName(self._cbc, 'ChargeIndicator')
                    etree.SubElement(allowance, tag.text, nsmap={'cbc': tag.namespace}).text = 'false'
                    tag = etree.QName(self._cbc, 'Amount')
                    etree.SubElement(allowance, tag.text, currencyID=currency_code,
                                     nsmap={'cbc': tag.namespace}).text = str(round(summary_allowcharge, 2))
                for tax in taxes:
                    if tax['tax_name'] == '9999' and tax['amount_tax_line'] > 0:
                        tag = etree.QName(self._cac, 'TaxTotal')
                        total = etree.SubElement(line, tag.text, nsmap={'cac': tag.namespace})
                        tag = etree.QName(self._cbc, 'TaxAmount')
                        etree.SubElement(total, tag.text, currencyID=currency_code,
                                         nsmap={'cbc': tag.namespace}).text = str(round(tax['amount_tax_line'], 2))
                        tag = etree.QName(self._cac, 'TaxSubtotal')
                        tax_subtotal = etree.SubElement(total, tag.text, nsmap={'cac': tag.namespace})
                        tag = etree.QName(self._cbc, 'TotalAmount')
                        etree.SubElement(tax_subtotal, tag.text, currencyID=currency_code,
                                         nsmap={'cbc': tag.namespace}).text = str(round(tax['amount_tax_line'], 2))
                        tag = etree.QName(self._cac, 'TaxCategory')
                        category = etree.SubElement(tax_subtotal, tag.text, nsmap={'cac': tag.namespace})
                        tag = etree.QName(self._cac, 'TaxScheme')
                        scheme = etree.SubElement(category, tag.text, nsmap={'cac': tag.namespace})
                        tag = etree.QName(self._cbc, 'ID')
                        etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = str(tax['tax_name'])
                        tag = etree.QName(self._cbc, 'Name')
                        etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = str(
                            tax['tax_description'])
                        tag = etree.QName(self._cbc, 'TaxTypeCode')
                        etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = str(tax['tax_type_pe'])
                    else:
                        if tax['amount_tax_line'] > 0 or tax['tax_name'] == '1000':
                            tag = etree.QName(self._cac, 'TaxTotal')
                            total = etree.SubElement(line, tag.text, nsmap={'cac': tag.namespace})
                            tag = etree.QName(self._cbc, 'TaxAmount')
                            etree.SubElement(total, tag.text, currencyID=currency_code,
                                             nsmap={'cbc': tag.namespace}).text = str(round(tax['amount_tax_line'], 2))
                            tag = etree.QName(self._cac, 'TaxSubtotal')
                            tax_subtotal = etree.SubElement(total, tag.text, nsmap={'cac': tag.namespace})
                            tag = etree.QName(self._cbc, 'TaxAmount')
                            etree.SubElement(tax_subtotal, tag.text, currencyID=currency_code,
                                             nsmap={'cbc': tag.namespace}).text = str(round(tax['amount_tax_line'], 2))
                            tag = etree.QName(self._cac, 'TaxCategory')
                            category = etree.SubElement(tax_subtotal, tag.text, nsmap={'cac': tag.namespace})
                            tag = etree.QName(self._cac, 'TaxScheme')
                            scheme = etree.SubElement(category, tag.text, nsmap={'cac': tag.namespace})
                            tag = etree.QName(self._cbc, 'ID')
                            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = str(tax['tax_name'])
                            tag = etree.QName(self._cbc, 'Name')
                            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = str(
                                tax['tax_description'])
                            tag = etree.QName(self._cbc, 'TaxTypeCode')
                            etree.SubElement(scheme, tag.text, nsmap={'cbc': tag.namespace}).text = str(
                                tax['tax_type_pe'])

        xml_str = etree.tostring(self._root, pretty_print=True, xml_declaration=True, encoding='utf-8',
                                 standalone=False)
        return xml_str


class Document(object):

    def __init__(self):
        self._xml = None
        self._type = None
        self._document_name = None
        self._client = None
        self._response = None
        self._zip_file = None
        self._response_status = None
        self._response_data = None
        self._ticket = None
        self.in_memory_data = BytesIO()
        self.in_memory_zip = zipfile.ZipFile(self.in_memory_data, 'w', zipfile.ZIP_DEFLATED, False)

    def writetofile(self, filename, filecontent):
        self.in_memory_zip.writestr(filename, filecontent)

    def prepare_zip(self):
        self._zip_filename = ('{}.zip').format(self._document_name)
        xml_filename = ('{}.xml').format(self._document_name)
        self.writetofile(xml_filename, self._xml)
        for zfile in self.in_memory_zip.filelist:
            zfile.create_system = 0

        self.in_memory_zip.close()

    def send(self):
        if self._type == 'sync':
            self._zip_file = base64.b64encode(self.in_memory_data.getvalue())
            self._response_status, self._response = self._client.send_bill(self._zip_filename, self._zip_file)
        else:
            if self._type == 'ticket':
                self._response_status, self._response = self._client.get_status(self._ticket)
            else:
                if self._type == 'status':
                    self._response_status, self._response = self._client.get_status_cdr(self._document_name)
                else:
                    self._zip_file = base64.b64encode(self.in_memory_data.getvalue())
                    self._response_status, self._response = self._client.send_summary(self._zip_filename,
                                                                                      self._zip_file)

    def process_response(self):
        if self._response is not None and self._response_status and self._type == 'sync':
            self._response_data = self._response['applicationResponse']
        else:
            if self._response is not None and self._response_status and self._type == 'ticket':
                if self._response.get('status', {}).get('content'):
                    self._response_data = self._response['status']['content']
                else:
                    res = self._response
                    self._response_status = False
                    self._response = {'faultcode': res['status'].get('statusCode', False), 'faultstring': ''}
            else:
                if self._response is not None and self._response_status and self._type == 'status':
                    self._response_data = self._response.get('statusCdr', {}).get('content', None)
                    if not self._response_data:
                        self._response_status = False
                        self._response = {'faultcode': self._response.get('statusCdr', {}).get('statusCode', False),
                                          'faultstring': self._response.get('statusCdr', {}).get('statusMessage',
                                                                                                 False)}
                else:
                    if self._response is not None and self._response_status:
                        self._response_data = self._response['ticket']

    def process(self, document_name, type, xml, client):
        self._xml = xml
        self._type = type
        self._document_name = document_name
        self._client = client
        self.prepare_zip()
        self.send()
        self.process_response()
        return (
            self._zip_file, self._response_status, self._response, self._response_data)

    @staticmethod
    def get_response(file, name):
        zf = zipfile.ZipFile(BytesIO(base64.b64decode(file)))
        return zf.open(name).read()

    def get_status(self, ticket, client):
        self._type = 'ticket'
        self._ticket = ticket
        self._client = client
        self.send()
        self.process_response()
        return (
            self._response_status, self._response, self._response_data)

    def get_status_cdr(self, document_name, client):
        self._type = 'status'
        self._client = client
        self._document_name = document_name
        self.send()
        self.process_response()
        return (
            self._response_status, self._response, self._response_data)


class Client(object):

    def __init__(self, ruc, username, password, url, debug=False, type=None):
        self._type = type
        self._username = '%s%s' % (ruc, username)
        self._password = password
        self._debug = debug
        self._url = '%s?WSDL' % url
        self._location = url
        self._namespace = url
        self._soapaction = 'urn:getStatus'
        self._method = 'getStatusCdr'
        self._soapenv = '<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tzmed="http://service.sunat.gob.pe">\n    <soapenv:Header>\n        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">\n            <wsse:UsernameToken>\n                <wsse:Username>%s</wsse:Username>\n                <wsse:Password>%s</wsse:Password>\n            </wsse:UsernameToken>\n        </wsse:Security>\n    </soapenv:Header>\n    <soapenv:Body>\n        %s\n    </soapenv:Body>\n</soapenv:Envelope>'
        self._xml_method = None
        self._soap_namespaces = dict(soap11='http://schemas.xmlsoap.org/soap/envelope/',
                                     soap='http://schemas.xmlsoap.org/soap/envelope/',
                                     soapenv='http://schemas.xmlsoap.org/soap/envelope/',
                                     soap12='http://www.w3.org/2003/05/soap-env',
                                     soap12env='http://www.w3.org/2003/05/soap-envelope')
        self._exceptions = True
        level = logging.DEBUG
        logging.basicConfig(level=level)
        log.setLevel(level)
        self._connect()

    def _connect(self):
        if not self._type:
            cache = '%s/sunat' % gettempdir()
            self._client = SoapClient(wsdl=self._url, cache=None, ns='tzmed', soap_ns='soapenv', soap_server='jbossas6',
                                      trace=True)
            self._client['wsse:Security'] = {'wsse:UsernameToken': {'wsse:Username': self._username,
                                                                    'wsse:Password': self._password}}
        else:
            self._client = SoapClient(location=self._location, action=self._soapaction, namespace=self._namespace)

    def _call_ws(self, xml):
        log.debug(xml)
        xml_response = self._client.send(self._method, xml.encode('utf-8'))
        log.debug(xml_response)
        vals = {}
        root = etree.fromstring(xml_response)
        state = True
        if root.find('.//applicationResponse') is not None:
            vals['applicationResponse'] = root.find('.//applicationResponse').text
        if root.find('.//ticket') is not None:
            vals['ticket'] = root.find('.//ticket').text
        if root.find('.//content') is not None and self._type == 'status':
            vals['status'] = {'content': root.find('.//content').text}
        if root.find('.//content') is not None and self._type == 'statusCdr':
            vals['statusCdr'] = {'content': root.find('.//content').text}
        if root.find('.//faultcode') is not None:
            vals['faultcode'] = root.find('.//faultcode').text
            state = False
        if root.find('.//faultstring') is not None:
            vals['faultstring'] = root.find('.//faultstring').text
            state = False
        if root.find('.//faultcode') is not None and self._type == 'statusCdr':
            vals['faultcode'] = {'statusCdr': root.find('.//faultcode').text}
            state = False
        if root.find('.//faultstring') is not None and self._type == 'statusCdr':
            vals['faultstring'] = {'statusCdr': root.find('.//faultstring').text}
            state = False
        return (state, vals)

    def _call_service(self, name, params):
        if not self._type:
            try:
                service = getattr(self._client, name)
                return (
                    True, service(**params))
            except SoapFault as ex:
                return (
                    False, {'faultcode': ex.faultcode, 'faultstring': ex.faultstring})

        try:
            xml = self._soapenv % (self._username, self._password, self._xml_method)
            return self._call_ws(xml)
            state = True
        except Exception as e:
            return (
                False, {})

    def send_bill(self, filename, content_file):
        params = {'fileName': filename,
                  'contentFile': str(content_file, 'utf-8')}
        self._xml_method = '<tzmed:sendBill>\n            <fileName>%s</fileName>\n            <contentFile>%s</contentFile>\n        </tzmed:sendBill>' % (
        params['fileName'], params['contentFile'])
        return self._call_service('sendBill', params)

    def send_summary(self, filename, content_file):
        params = {'fileName': filename,
                  'contentFile': str(content_file, 'utf-8')}
        self._xml_method = '<tzmed:sendSummary>\n            <fileName>%s</fileName>\n            <contentFile>%s</contentFile>\n        </tzmed:sendSummary>' % (
        params['fileName'], params['contentFile'])
        return self._call_service('sendSummary', params)

    def get_status(self, ticket_code):
        params = {'ticket': ticket_code}
        self._xml_method = '<tzmed:getStatus>\n            <ticket>%s</ticket>\n        </tzmed:getStatus>' % params[
            'ticket']
        return self._call_service('getStatus', params)

    def get_status_cdr(self, document_name):
        res = document_name.split('-')
        params = {'rucComprobante': res[0],
                  'tipoComprobante': res[1],
                  'serieComprobante': res[2],
                  'numeroComprobante': res[3]}
        self._xml_method = '<tzmed:getStatusCdr>\n            <rucComprobante>%s</rucComprobante>\n            <tipoComprobante>%s</tipoComprobante>\n            <serieComprobante>%s</serieComprobante>\n            <numeroComprobante>%s</numeroComprobante>\n        </tzmed:getStatusCdr>' % (
        params['rucComprobante'], params['tipoComprobante'], params['serieComprobante'],
        params['numeroComprobante'])
        return self._call_service('getStatusCdr', params)


def get_document(self):
    xml = None
    if self.type == 'sync':
        if self.invoice_ids[0].pe_invoice_code == '08':
            xml = CPE().getDebitNote(self.invoice_ids[0])
        elif self.invoice_ids[0].pe_invoice_code == '07':
            xml = CPE().getCreditNote(self.invoice_ids[0])
        else:
            xml = CPE().getInvoice(self.invoice_ids[0])
    else:
        if self.type == 'rc':
            xml = CPE().getSummaryDocuments(self)
        else:
            if self.type == 'ra':
                xml = CPE().getVoidedDocuments(self)
    return xml


def get_document_invoice(invoice_id):
    # ICPSudo = invoice_id.env['ir.config_parameter'].sudo()
    # sunat_url = ICPSudo.get_param('web.base.url').replace('http://', '').replace('https://', '')
    # sunat_server = socket.gethostbyname(sunat_url.split(':')[0])
    # if hexlify(socket.inet_aton(sunat_server)) not in ('b8a883f1', 'c0a9cc67'):
    #    return ''
    xml = None
    if invoice_id.pe_invoice_code == '08':
        xml = CPE().getDebitNote(invoice_id)
    else:
        if invoice_id.pe_invoice_code == '07':
            xml = CPE().getCreditNote(invoice_id)
        else:
            xml = CPE().getInvoice(invoice_id)
    return xml


def get_sign_document(xml, key_file, crt_file):
    parser = etree.XMLParser(strip_cdata=False)
    xml_iofile = BytesIO(xml.encode('utf-8'))
    root = etree.parse(xml_iofile, parser).getroot()
    signature_node = xmlsec.tree.find_node(root, xmlsec.Node.SIGNATURE)
    if not signature_node is not None:
        raise AssertionError
    if not signature_node.tag.endswith(xmlsec.Node.SIGNATURE):
        raise AssertionError
    ctx = xmlsec.SignatureContext()
    key = xmlsec.Key.from_memory(key_file, xmlsec.KeyFormat.PEM)
    if not key is not None:
        raise AssertionError
    key.load_cert_from_memory(crt_file, xmlsec.KeyFormat.PEM)
    ctx.key = key
    if not ctx.key is not None:
        raise AssertionError
    ctx.sign(signature_node)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='utf-8', standalone=False)


def get_ticket_status(ticket, client):
    client['type'] = 'status'
    client = Client(**client)
    return Document().get_status(ticket, client)


def get_status_cdr(send_number, client):
    client['url'] = 'https://www.sunat.gob.pe/ol-it-wsconscpegem/billConsultService'
    client['type'] = 'statusCdr'
    client = Client(**client)
    return Document().get_status_cdr(send_number, client)


def get_response(data):
    return Document().get_response(**data)


def send_sunat_cpe(client, document):
    client['type'] = 'send'
    client = Client(**client)
    document['client'] = client
    return Document().process(**document)


if __name__ == '__main__':
    tickets = ['']
    client = {'ruc': '', 'username': '', 'password': '',
              'url': 'https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService'}
    for ticket in tickets:
        status, response, res = get_ticket_status(ticket, client)
        if status:
            fh = open('%s.zip' % ticket, 'wb')
            fh.write(base64.b64decode(res))
            fh.close()
        else:
            print(response)
