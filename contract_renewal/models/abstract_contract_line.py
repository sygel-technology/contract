# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractAbstractContractLine(models.AbstractModel):
    _inherit = "contract.abstract.contract.line"

    is_auto_renew = fields.Boolean(string="Auto Renew", default=False)
    auto_renew_interval = fields.Integer(
        default=1,
        string="Renew Every",
        help="Renew every (Days/Week/Month/Year)",
    )
    auto_renew_rule_type = fields.Selection(
        [
            ("daily", "Day(s)"),
            ("weekly", "Week(s)"),
            ("monthly", "Month(s)"),
            ("yearly", "Year(s)"),
        ],
        default="yearly",
        string="Renewal type",
        help="Specify Interval for automatic renewal.",
    )
