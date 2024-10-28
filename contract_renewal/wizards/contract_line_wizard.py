# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractLineWizard(models.TransientModel):
    _inherit = "contract.line.wizard"

    manual_renew_needed = fields.Boolean(
        default=False,
        help="This flag is used to make a difference between a definitive stop"
        "and temporary one for which a user is not able to plan a"
        "successor in advance",
    )

    def _get_stop_extra_vals(self):
        vals = super()._get_stop_extra_vals()
        vals["manual_renew_needed"] = self.manual_renew_needed
        return vals
