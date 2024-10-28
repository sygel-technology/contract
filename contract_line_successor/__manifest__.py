# Copyright 2004-2010 OpenERP SA
# Copyright 2014-2018 Tecnativa - Pedro M. Baeza
# Copyright 2015 Domatix
# Copyright 2016-2018 Tecnativa - Carlos Dauden
# Copyright 2017 Tecnativa - Vicent Cubells
# Copyright 2016-2017 LasLabs Inc.
# Copyright 2018-2019 ACSONE SA/NV
# Copyright 2020-2021 Tecnativa - Pedro M. Baeza
# Copyright 2020 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Recurring - Contracts Successor",
    "version": "17.0.1.0.0",
    "category": "Contract Management",
    "license": "AGPL-3",
    "author": "Tecnativa, ACSONE SA/NV, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/contract",
    "depends": ["contract_renewal"],
    "development_status": "Production/Stable",
    "data": [
        "wizards/contract_line_wizard_views.xml",
        "views/contract_line_views.xml",
        "views/contract_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
}
