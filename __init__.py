# -*- coding: utf-8 -*-
"""
    __init__.py

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool

from product import Template
from rental import RentalContract, RentalContractLine


def register():
    Pool.register(
        Template,
        RentalContract,
        RentalContractLine,
        module='rental', type_='model'
    )
