# -*- coding: utf-8 -*-
"""
    stock.py

    :copyright: (c) 2015 by Fulfil.IO Inc.
    :license: see LICENSE.
"""
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta


class Move:
    __name__ = 'stock.move'

    @classmethod
    def _get_origin(cls):
        models = super(Move, cls)._get_origin()
        models.append('rental.contract.line')
        return models
