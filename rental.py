# -*- coding: utf-8 -*-
"""
    rental.py

    :copyright: (c) 2015 by Fulfil.IO Inc.
    :license: see LICENSE.
"""
from decimal import Decimal
from itertools import groupby, chain
from functools import partial

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool


__all__ = ['RentalContract', 'RentalContractLine']


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
        ('reservation', 'Reservation'),
        ('active', 'Active'),
        ('close', 'Close'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
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

    warehouse = fields.Many2One(
        'stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], states={
            'readonly': Eval('state') != 'draft',
        }, depends=['state'])

    start_date = fields.DateTime(
        'Start Date', depends=['state'], states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
        }
    )
    end_date = fields.DateTime(
        'End Date', depends=['state'], states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
        }
    )
    duration = fields.Function(
        fields.Integer('Duration'), 'on_change_with_duration'
    )

    billing_method = fields.Selection([
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], 'Billing Method', required=True, select=True, states={
        'readonly': ~Eval('state').in_(['draft', 'quotation']),
    })

    lines = fields.One2Many(
        'rental.contract.line', 'rental_contract', 'Lines', states={
            'readonly': Eval('state') != 'draft',
        }, depends=['state']
    )
    invoices = fields.Function(
        fields.One2Many('account.invoice', None, 'Invoices'),
        getter='get_invoices', searcher='search_invoices',
    )
    shipments = fields.Function(
        fields.One2Many('stock.shipment.out', None, 'Shipments'),
        getter='get_shipments', searcher='search_shipments',
    )
    shipment_returns = fields.Function(
        fields.One2Many('stock.shipment.out.return', None, 'Shipment Returns'),
        'get_shipment_returns', searcher='search_shipment_returns'
    )
    moves = fields.Function(
        fields.One2Many('stock.move', None, 'Moves'),
        'get_moves'
    )

    def get_moves(self, name):
        return [m.id for l in self.lines for m in l.moves]

    def search_shipments_returns(model_name):
        def method(self, name, clause):
            return [
                ('lines.moves.shipment.id',) + tuple(clause[1:])
                + (model_name,)
            ]
        return classmethod(method)

    search_shipments = search_shipments_returns('stock.shipment.out')
    search_shipment_returns = search_shipments_returns(
        'stock.shipment.out.return'
    )

    def get_shipments_returns(model_name):
        "Computes the returns or shipments"
        def method(self, name):
            Model = Pool().get(model_name)
            shipments = set()
            for line in self.lines:
                for move in line.moves:
                    if isinstance(move.shipment, Model):
                        shipments.add(move.shipment.id)
            return list(shipments)
        return method

    get_shipments = get_shipments_returns('stock.shipment.out')
    get_shipment_returns = get_shipments_returns('stock.shipment.out.return')

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_billing_type():
        return 'one_time'

    @staticmethod
    def default_billing_method():
        return 'hourly'

    @staticmethod
    def default_billing_frequency():
        return 1

    @fields.depends('billing_method', 'start_date', 'end_date')
    def on_change_with_duration(self, name=None):
        if not (self.end_date and self.start_date):
            return 0

        timedelta = self.end_date - self.start_date

        if self.billing_method == 'hourly':
            return timedelta.seconds / 3600
        elif self.billing_method == 'daily':
            return timedelta.days
        elif self.billing_method == 'weekly':
            return timedelta.days / 7
        elif self.billing_method == 'monthly':
            return timedelta.days / 30
        elif self.billing_method == 'yearly':
            return timedelta.days / 365

    @classmethod
    def __setup__(cls):
        super(RentalContract, cls).__setup__()
        cls._transitions |= set((
            ('draft', 'quotation'),
            ('quotation', 'reservation'),
            ('reservation', 'active'),
            ('active', 'close'),
            ('reservation', 'cancel'),
            ('quotation', 'cancel'),
            ('quotation', 'draft'),
            ('cancel', 'draft'),
        ))
        cls._buttons.update({
            'cancel': {
                'invisible': ~Eval('state').in_(
                    ['draft', 'quotation', 'reservation']
                )},
            'draft': {
                'invisible': ~Eval('state').in_(['cancel', 'quotation']),
                'icon': If(
                    Eval('state') == 'cancel', 'tryton-clear',
                    'tryton-go-previous'
                )},
            'quote': {
                'invisible': Eval('state') != 'draft',
                'readonly': ~Eval('lines', []),
                },
            'reserve': {
                'invisible': Eval('state') != 'quotation',
                },
            'active': {
                'invisible': Eval('state') != 'reservation',
                },
            'close': {
                'invisible': Eval('state') != 'active',
                },
        })

    def get_invoices(self, name):
        invoices = set()
        for line in self.lines:
            for invoice_line in line.invoice_lines:
                if invoice_line.invoice:
                    invoices.add(invoice_line.invoice.id)
        return list(invoices)

    @classmethod
    def search_invoices(cls, name, clause):
        return [('lines.invoice_lines.invoice.id',) + tuple(clause[1:])]

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
            invoice_address = shipment_address = self.party.address_get()

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

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, contracts):
        ShipmentOut = Pool().get('stock.shipment.out')
        ShipmentOutReturn = Pool().get('stock.shipment.out.return')

        for contract in contracts:
            ShipmentOut.cancel(contract.shipments)
            ShipmentOutReturn.cancel(contract.shipment_returns)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, contracts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, contracts):
        for contract in contracts:
            contract.set_reference()

    def set_reference(self):
        Sequence = Pool().get('ir.sequence')
        Configuration = Pool().get('rental.configuration')

        if not self.reference:
            self.write([self], {
                'reference': Sequence.get_id(
                    Configuration(1).contract_sequence.id
                ),
            })

    @classmethod
    @ModelView.button
    @Workflow.transition('reservation')
    def reserve(cls, contracts):
        for contract in contracts:
            contract.create_invoice('out_invoice')
            contract.create_shipment('out')
            contract.create_shipment('return')

    @classmethod
    @ModelView.button
    @Workflow.transition('active')
    def active(cls, contracts):
        ShipmentOut = Pool().get('stock.shipment.out')

        for contract in contracts:
            ShipmentOut.assign(contract.shipments)
            ShipmentOut.pack(contract.shipments)
            ShipmentOut.done(contract.shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('close')
    def close(cls, contracts):
        ShipmentOutReturn = Pool().get('stock.shipment.out.return')

        for contract in contracts:
            ShipmentOutReturn.receive(contract.shipment_returns)
            ShipmentOutReturn.done(contract.shipment_returns)

    def _get_invoice_line_rent_line(self, invoice_type):
        '''
        Return invoice line for each rent lines according to invoice_type
        '''
        res = {}
        for line in self.lines:
            val = line.get_invoice_line(invoice_type)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_rent(self, invoice_type):
        Invoice = Pool().get('account.invoice')
        Configuration = Pool().get('rental.configuration')

        return Invoice(
            company=self.company,
            type=invoice_type,
            journal=Configuration(1).subscription_journal,
            party=self.party,
            invoice_address=self.invoice_address,
            currency=self.currency,
            account=self.party.account_receivable,
            description='Contract  #%s' % self.reference,
            payment_term=self.party.customer_payment_term or
                Configuration(1).subscription_invoice_payment_term,  # noqa
        )

    def create_invoice(self, invoice_type):
        invoice_lines = self._get_invoice_line_rent_line(invoice_type)
        if not invoice_lines:
            return

        invoice = self._get_invoice_rent(invoice_type)
        invoice.lines = (
            (list(invoice.lines) if hasattr(invoice, 'lines') else [])
            + list(chain.from_iterable(invoice_lines.itervalues()))
        )
        invoice.save()

        return invoice

    def _group_shipment_key(self, moves, move):
        '''
        The key to group moves by shipments
        move is a tuple of line id and a move
        '''
        ContractLine = Pool().get('rental.contract.line')

        line_id, move = move
        line = ContractLine(line_id)

        planned_date = max(m.planned_date for m in moves)
        return (
            ('planned_date', planned_date),
            ('warehouse', line.rental_contract.warehouse.id),
        )

    def _get_shipment_rent(self, Shipment, key):
        values = {
            'customer': self.party.id,
            'delivery_address': self.shipment_address.id,
            'company': self.company.id,
            }
        values.update(dict(key))
        return Shipment(**values)

    def create_shipment(self, shipment_type):
        moves = self._get_move_rent_line(shipment_type)

        if not moves:
            return
        if shipment_type == 'out':
            keyfunc = partial(self._group_shipment_key, moves.values())
            Shipment = Pool().get('stock.shipment.out')
        elif shipment_type == 'return':
            keyfunc = partial(self._group_shipment_key, moves.values())
            Shipment = Pool().get('stock.shipment.out.return')

        moves = moves.items()
        moves = sorted(moves, key=keyfunc)

        shipments = []
        for key, grouped_moves in groupby(moves, key=keyfunc):
            shipment = self._get_shipment_rent(Shipment, key)
            shipment.moves = (
                list(getattr(shipment, 'moves', []))
                + [x[1] for x in grouped_moves]
            )
            shipment.save()
            shipments.append(shipment)
        if shipment_type == 'out':
            Shipment.wait(shipments)
        return shipments

    def _get_move_rent_line(self, shipment_type):
        res = {}
        for line in self.lines:
            val = line.get_move(shipment_type)
            if val:
                res[line.id] = val
        return res


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
        'Rent', digits=(16, 4),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
        }, depends=['type']
    )
    amount = fields.Function(fields.Numeric("Amount"), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    invoice_lines = fields.One2Many(
        'account.invoice.line', 'origin',
        'Invoice Lines', readonly=True
    )
    moves = fields.One2Many(
        'stock.move', 'origin', 'Moves', readonly=True
    )

    @staticmethod
    def default_type():
        return 'line'

    @staticmethod
    def default_sequence():
        return 10

    def get_amount(self, name):
        if self.type == 'line':
            return self.on_change_with_amount()

    @staticmethod
    def default_unit_digits():
        return 2

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    def _get_context_rent(self):
        context = {}
        if getattr(self, 'rental_contract', None):
            if getattr(self.rental_contract, 'currency', None):
                context['currency'] = self.rental_contract.currency.id
            if getattr(self.rental_contract, 'party', None):
                context['customer'] = self.rental_contract.party.id
            if getattr(self.rental_contract, 'billing_method', None):
                context['billing_method'] = self.rental_contract.billing_method
            if getattr(self.rental_contract, 'start_date', None):
                context['contract_start_date'] = \
                    self.rental_contract.start_date.date()
        if self.unit:
            context['uom'] = self.unit.id
        else:
            context['uom'] = self.product.default_uom.id
        return context

    @fields.depends(
        'product', 'unit', 'quantity', 'description',
        '_parent_rental_contract.party', '_parent_rental_contract.currency',
        '_parent_rental_contract.billing_method'
    )
    def on_change_product(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        party = None
        party_context = {}
        if self.rental_contract and self.rental_contract.party:
            party = self.rental_contract.party
            if party.lang:
                party_context['language'] = party.lang.code

        category = self.product.default_uom.category
        if not self.unit or self.unit not in category.uoms:
            res['unit'] = self.product.default_uom.id
            self.unit = self.product.default_uom
            res['unit.rec_name'] = self.product.default_uom.rec_name
            res['unit_digits'] = self.product.default_uom.digits

        with Transaction().set_context(self._get_context_rent()):
            res['unit_price'] = Product.get_rent(
                [self.product],
                self.quantity or 0
            )[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])

        if not self.description:
            with Transaction().set_context(party_context):
                res['description'] = Product(self.product.id).rec_name

        self.unit_price = res['unit_price']
        self.type = 'line'
        res['amount'] = self.on_change_with_amount()
        return res

    @fields.depends(
        'type', 'quantity', 'unit_price', 'unit',
        '_parent_rental_contract.currency'
    )
    def on_change_with_amount(self):
        if self.type == 'line':
            currency = self.rental_contract.currency if self.rental_contract \
                else None
            amount = Decimal(str(self.quantity or '0.0')) * \
                (self.unit_price or Decimal('0.0'))
            if currency:
                return currency.round(amount)
            return amount
        return Decimal('0.0')

    def get_invoice_line(self, invoice_type):
        '''
        Return a list of invoice lines for rent line according to invoice_type
        '''
        InvoiceLine = Pool().get('account.invoice.line')

        if self.type != 'line' or self.quantity < 0:
            # TODO: Handle other cases
            return []

        invoice_line = InvoiceLine()
        invoice_line.type = self.type
        invoice_line.description = self.description
        invoice_line.note = self.note
        invoice_line.origin = self
        invoice_line.quantity = self.quantity
        invoice_line.unit = self.unit
        invoice_line.product = self.product
        invoice_line.unit_price = Decimal(
            self.unit_price * self.rental_contract.duration
        )
        invoice_line.invoice_type = invoice_type
        invoice_line.account = self.product.account_revenue_used
        return [invoice_line]

    def get_move(self, shipment_type):
        '''
        Return moves for the rent line according to shipment_type
        '''
        Move = Pool().get('stock.move')
        Configuration = Pool().get('rental.configuration')

        if self.type != 'line':
            return
        if not self.product or not self.quantity:
            return

        if self.product.type == 'service':
            return

        if shipment_type == 'out':
            planned_date = self.rental_contract.start_date.date()
        elif shipment_type == 'return':
            planned_date = self.rental_contract.end_date.date()

        move = Move()
        move.quantity = self.quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.rental_contract.warehouse.output_location.id
        move.to_location = Configuration(1).rent_location.id
        move.state = 'draft'
        move.company = self.rental_contract.company.id
        move.unit_price = self.unit_price
        move.currency = self.rental_contract.currency
        move.planned_date = planned_date
        move.invoice_lines = self.invoice_lines
        move.origin = self
        return move
