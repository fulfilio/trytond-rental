# -*- coding: utf-8 -*-
"""
    product.py

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__metaclass__ = PoolMeta
__all__ = ['Template']


class Template:
    __name__ = 'product.template'

    rentable = fields.Boolean(
        'Rentable', states={
            'readonly': ~Eval('active', True),
        }, depends=['active']
    )
