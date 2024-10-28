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
    "name": "Recurring - Contracts Renewal",
    "version": "17.0.1.1.0",
    "category": "Auto-renew contracts",
    "license": "AGPL-3",
    "author": "Tecnativa, ACSONE SA/NV, Sygel, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/contract",
    "depends": ["contract"],
    "development_status": "Production/Stable",
    "data": [
        "data/contract_renew_cron.xml",
        "wizards/contract_line_wizard_views.xml",
        "views/abstract_contract_line_views.xml",
        "views/contract_views.xml",
        "views/contract_line_views.xml",
        "views/contract_template_views.xml",
    ],
    "assets": {
        "web.assets_frontend": ["contract/static/src/scss/frontend.scss"],
        "web.assets_tests": ["contract/static/src/js/contract_portal_tour.esm.js"],
    },
    "installable": True,
}
