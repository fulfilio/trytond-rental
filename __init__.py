# -*- coding: utf-8 -*-
"""
    __init__.py

    :copyright: (c) 2015 by Fulfil.IO Inc.
    :license: see LICENSE.
"""
from trytond.pool import Pool

from product import Template, Product
from rental import RentalContract, RentalContractLine
from configuration import Configuration
from invoice import InvoiceLine


def register():
    Pool.register(
        Template,
        Product,
        Configuration,
        RentalContract,
        RentalContractLine,
        InvoiceLine,
        module='rental', type_='model'
    )
