# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractLineWizard(models.TransientModel):
    _inherit = "contract.line.wizard"

    is_auto_renew = fields.Boolean(default=False)

    def plan_successor(self):
        for wizard in self:
            wizard.contract_line_id.plan_successor(
                wizard.date_start, wizard.date_end, wizard.is_auto_renew
            )
        return True

    def stop_plan_successor(self):
        for wizard in self:
            wizard.contract_line_id.stop_plan_successor(
                wizard.date_start, wizard.date_end, wizard.is_auto_renew
            )
        return True
