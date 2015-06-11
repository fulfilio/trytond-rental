# -*- coding: utf-8 -*-
"""
    rental.py

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool


__all__ = ['RentalContract']


class RentalContract(Workflow, ModelSQL, ModelView):
    'Rental Contract'
    __name__ = 'rental.contract'
    _rec_name = 'reference'

    company = fields.Many2One(
        'company.company', 'Company', required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
        }, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
        ], depends=['state'], select=True
    )
    currency = fields.Many2One(
        'currency.currency', 'Currency', required=True, states={
            'readonly': (
                (Eval('state') != 'draft') |
                (Eval('lines', [0]) & Eval('currency', 0))
            ),
        }, depends=['state']
    )
    reference = fields.Char('Reference', readonly=True, select=True)
    description = fields.Char(
        'Description', depends=['state'], states={
            'readonly': Eval('state') != 'draft',
        },
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
    contract_date = fields.Date(
        'Contract Date', depends=['state'], states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
        }
    )
    party = fields.Many2One(
        'party.party', 'Party', required=True, select=True, states={
            'readonly': (
                (Eval('state') != 'draft') |
                (Eval('lines', [0]) & Eval('party'))
            )
        }, depends=['state']
    )
    invoice_address = fields.Many2One(
        'party.address', 'Invoice Address',
        domain=[('party', '=', Eval('party'))], states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
        }, depends=['state', 'party']
    )
    shipment_address = fields.Many2One(
        'party.address', 'Shipment Address',
        domain=[('party', '=', Eval('party'))], states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
        },
        depends=['party', 'state']
    )

    start_date = fields.Date(
        'Start Date', depends=['state'], states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
        }
    )
    end_date = fields.Date(
        'End Date', depends=['state'], states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
        }
    )
    lines = fields.One2Many(
        'rental.contract.line', 'rental_contract', 'Lines', states={
            'readonly': Eval('state') != 'draft',
        }, depends=['state']
    )

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @fields.depends('party')
    def on_change_party(self):
        invoice_address = None
        shipment_address = None
        if self.party:
            invoice_address = self.party.address_get(type='invoice')
            shipment_address = self.party.address_get(type='delivery')

        changes = {}
        if invoice_address:
            changes['invoice_address'] = invoice_address.id
            changes['invoice_address.rec_name'] = invoice_address.rec_name
        else:
            changes['invoice_address'] = None
        if shipment_address:
            changes['shipment_address'] = shipment_address.id
            changes['shipment_address.rec_name'] = shipment_address.rec_name
        else:
            changes['shipment_address'] = None
        return changes

    def get_rec_name(self, name):
        return (
            self.reference or str(self.id) + ' - ' + self.party.rec_name
        )


class RentalContractLine(ModelSQL, ModelView):
    "Rental Contract Line"
    __name__ = "rental.contract.line"
    _rec_name = 'description'

    rental_contract = fields.Many2One(
        'rental.contract', 'Rental Contract', ondelete='CASCADE', select=True
    )
    sequence = fields.Integer('Sequence')
    type = fields.Selection([
        ('line', 'Line'),
        ], 'Type', select=True, required=True
    )
    quantity = fields.Float(
        'Quantity', digits=(16, Eval('unit_digits', 2)),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': ~Eval('_parent_rental_contract', {}),
        }, depends=['type', 'unit_digits']
    )
    unit = fields.Many2One(
        'product.uom', 'Unit',
        states={
            'required': Bool(Eval('product')),
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_rental_contract', {}),
        }, domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product', 'type', 'product_uom_category']
    )
    unit_digits = fields.Function(
        fields.Integer('Unit Digits'),
        'on_change_with_unit_digits'
    )
    product = fields.Many2One(
        'product.product', 'Product',
        domain=[('rentable', '=', True)],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_rental_contract', {}),
        }, depends=['type']
    )
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category'
    )
    unit_price = fields.Numeric(
        'Unit Price', digits=(16, 4),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
        }, depends=['type']
    )
    description = fields.Text('Description', size=None, required=True)

    @staticmethod
    def default_unit_digits():
        return 2

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2
