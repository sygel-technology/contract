# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ContractContract(models.Model):
    _inherit = "contract.contract"

    def _convert_contract_lines(self, contract):
        new_lines = super()._convert_contract_lines(contract)
        new_lines._onchange_is_auto_renew()
        return new_lines
