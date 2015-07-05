# -*- coding: utf-8 -*-
"""
    invoice.py

    :copyright: (c) 2015 by Fulfil.IO Inc.
    :license: see LICENSE.
"""
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = "account.invoice.line"

    @classmethod
    def _get_origin(cls):
        models = super(InvoiceLine, cls)._get_origin()
        models.append('rental.contract.line')
        return models
