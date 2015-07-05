# -*- coding: utf-8 -*-
"""
    product.py

    :copyright: (c) 2015 by Fulfil.IO Inc.
    :license: see LICENSE.
"""
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval, Bool, Not
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = ['Template', 'Product']

STATES = {
    'required': Bool(Eval('rentable')),
    'invisible': Not(Bool(Eval('rentable'))),
}


class Template:
    __name__ = 'product.template'

    rentable = fields.Boolean(
        'Rentable', states={
            'readonly': ~Eval('active', True),
        }, depends=['active']
    )
    rent_hourly = fields.Numeric(
        'Rent Hourly', digits=(16, 4), states=STATES,
        depends=['rentable'],
    )
    rent_daily = fields.Numeric(
        'Rent Daily', digits=(16, 4), states=STATES,
        depends=['rentable'],
    )
    rent_weekly = fields.Numeric(
        'Rent Weekly', digits=(16, 4), states=STATES,
        depends=['rentable'],
    )
    rent_monthly = fields.Numeric(
        'Rent Monthly', digits=(16, 4), states=STATES,
        depends=['rentable'],
    )
    rent_yearly = fields.Numeric(
        'Rent Yearly', digits=(16, 4), states=STATES,
        depends=['rentable'],
    )

    @staticmethod
    def default_rent_hourly():
        return Decimal('0')

    @staticmethod
    def default_rent_daily():
        return Decimal('0')

    @staticmethod
    def default_rent_weekly():
        return Decimal('0')

    @staticmethod
    def default_rent_monthly():
        return Decimal('0')

    @staticmethod
    def default_rent_yearly():
        return Decimal('0')


class Product:
    __name__ = 'product.product'

    @staticmethod
    def get_rent(products, quantity=0):
        '''
        Return the rent price for products and quantity.
        It uses if exists from the context:
            currency: the currency id for the returned price
            billing_method: hourly, daily, weekly, monthly, yearly
        '''
        User = Pool().get('res.user')
        Currency = Pool().get('currency.currency')
        Date = Pool().get('ir.date')

        today = Date.today()
        prices = {}

        currency = None
        if Transaction().context.get('currency'):
            currency = Currency(Transaction().context.get('currency'))

        user = User(Transaction().user)

        for product in products:
            prices[product.id] = getattr(
                product, 'rent_%s' % Transaction().context.get('billing_method')
            )
            if currency and user.company:
                if user.company.currency != currency:
                    date = Transaction().context.get('contract_start_date') or \
                        today
                    with Transaction().set_context(date=date):
                        prices[product.id] = Currency.compute(
                            user.company.currency, prices[product.id],
                            currency, round=False)
        return prices
