# -*- coding: utf-8 -*-
"""
    configuration.py

    :copyright: (c) 2015 by Fulfil.IO Inc.
    :license: see LICENSE.
"""
from trytond.model import ModelSingleton, ModelSQL, ModelView, fields

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Rental Configuration'
    __name__ = 'rental.configuration'

    contract_sequence = fields.Property(
        fields.Many2One(
            'ir.sequence', 'Contract Sequence',
            help='Sequence for rental contracts',
            required=True
        )
    )
    subscription_invoice_payment_term = fields.Property(
        fields.Many2One(
            'account.invoice.payment_term',
            'Subscription Invoice Payment Term',
            required=True,
            help="This payment term will be used if customer does not have one."
        )
    )
    subscription_journal = fields.Property(
        fields.Many2One(
            'account.journal', 'Subscription Journal',
            required=True,
        )
    )
