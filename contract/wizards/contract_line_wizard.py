# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractLineWizard(models.TransientModel):
    _name = "contract.line.wizard"
    _description = "Contract Line Wizard"

    date_start = fields.Date()
    date_end = fields.Date()
    recurring_next_date = fields.Date(string="Next Invoice Date")
    contract_line_id = fields.Many2one(
        comodel_name="contract.line",
        string="Contract Line",
        required=True,
        index=True,
        ondelete="cascade",
    )

    def _get_stop_extra_vals(self):
        self.ensure_one()
        return {}

    def stop(self):
        for wizard in self:
            wizard.contract_line_id.stop(
                wizard.date_end, **wizard._get_stop_extra_vals()
            )
        return True

    def uncancel(self):
        for wizard in self:
            wizard.contract_line_id.uncancel(wizard.recurring_next_date)
        return True
