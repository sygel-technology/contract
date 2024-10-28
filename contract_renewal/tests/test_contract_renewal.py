# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError

from odoo.addons.contract.tests.test_contract import TestContractBase


class TestContractRenewal(TestContractBase):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass()
        # cls.line_vals["is_auto_renew"] = False
        cls.contract_line = cls.contract.contract_line_ids[0]
        cls.contract_line_states = [
            state[0] for state in cls.env["contract.line"]._fields["state"].selection
        ]

    def test_to_renew_state(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        self.assertEqual(self.contract_line.state, "closed")
        self.contract_line.is_auto_renew = True
        self.contract_line.manual_renew_needed = False
        self.assertEqual(self.contract_line.state, "to-renew")
        self.contract_line.is_auto_renew = False
        self.contract_line.manual_renew_needed = True
        self.assertEqual(self.contract_line.state, "to-renew")

    def test_stop_auto_renew(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(years=1)
        self.contract_line.is_auto_renew = True
        self.contract_line.stop(fields.Date.today() + relativedelta(days=1))
        self.assertEqual(
            self.contract_line.date_end, fields.Date.today() + relativedelta(days=1)
        )
        self.assertFalse(self.contract_line.is_auto_renew)

    def test_domain_renew_to_renew(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        self.contract_line.is_auto_renew = True
        self.contract_line.manual_renew_needed = False
        domain = self.contract_line._get_state_domain("to-renew")
        lines = self.contract_line.search(domain)
        self.assertTrue(self.contract_line.id in lines.ids)
        self.contract_line_states.remove("to-renew")
        for state in self.contract_line_states:
            domain = self.contract_line._get_state_domain(state)
            lines = self.contract_line.search(domain)
            self.assertFalse(self.contract_line.id in lines.ids)

    def test_domain_upcoming_close(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=2)
        domain = self.contract_line._get_state_domain("upcoming-close")
        lines = self.contract_line.search(domain)
        self.assertTrue(self.contract_line.id in lines.ids)
        self.contract_line_states.remove("upcoming-close")
        for state in self.contract_line_states:
            domain = self.contract_line._get_state_domain(state)
            lines = self.contract_line.search(domain)
            self.assertFalse(self.contract_line.id in lines.ids)

    def test_domain_in_progress(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(months=2)
        domain = self.contract_line._get_state_domain("in-progress")
        lines = self.contract_line.search(domain)
        self.assertTrue(self.contract_line.id in lines.ids)
        self.contract_line_states.remove("in-progress")
        for state in self.contract_line_states:
            domain = self.contract_line._get_state_domain(state)
            lines = self.contract_line.search(domain)
            self.assertFalse(self.contract_line.id in lines.ids)

    def test_domain_in_closed(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        domain = self.contract_line._get_state_domain("closed")
        lines = self.contract_line.search(domain)
        self.assertTrue(self.contract_line.id in lines.ids)
        self.contract_line_states.remove("closed")
        for state in self.contract_line_states:
            domain = self.contract_line._get_state_domain(state)
            lines = self.contract_line.search(domain)
            self.assertFalse(self.contract_line.id in lines.ids)

    def test_cancel(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(years=1)
        self.contract_line.is_auto_renew = True
        self.contract_line.cancel()
        domain = self.contract_line._get_state_domain("canceled")
        self.assertTrue(self.contract_line.id in self.contract_line.search(domain).ids)
        self.assertEqual(self.contract_line.state, "canceled")
        self.assertTrue(self.contract_line.is_canceled)
        self.assertFalse(self.contract_line.is_auto_renew)

    def test_date_end(self):
        self.contract_line.date_start = fields.Date.today()
        self.contract_line.date_end = fields.Date.today() + relativedelta(years=2)
        self.contract_line.auto_renew_rule_type = "yearly"
        self.contract_line.auto_renew_interval = 1
        self.contract_line.is_auto_renew = True
        self.contract_line._onchange_is_auto_renew()
        self.assertEqual(
            fields.Date.today() + relativedelta(years=1) + relativedelta(days=-1),
            self.contract_line.date_end,
        )

    def test_cron_renew(self):
        self.contract_line.date_start = (
            fields.Date.today() + relativedelta(years=-1) + relativedelta(days=-1)
        )
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        self.contract_line.auto_renew_rule_type = "yearly"
        self.contract_line.auto_renew_interval = 1
        self.contract_line.is_auto_renew = True
        self.assertEqual(self.contract_line.state, "to-renew")
        self.contract_line.cron_renew_contract_line()
        self.assertEqual(self.contract_line.state, "in-progress")
        self.assertEqual(
            self.contract_line.date_end,
            fields.Date.today() + relativedelta(years=1) + relativedelta(days=-1),
        )

    def test_stop_renew(self):
        self.assertFalse(self.contract_line.manual_renew_needed)
        self.contract_line.write(
            {
                "date_start": self.today,
                "date_end": self.today + relativedelta(months=5),
            }
        )
        wizard = self.env["contract.line.wizard"].create(
            {
                "date_end": self.today + relativedelta(months=3),
                "contract_line_id": self.contract_line.id,
                "manual_renew_needed": True,
            }
        )
        wizard.stop()
        self.assertEqual(
            self.contract_line.date_end, self.today + relativedelta(months=3)
        )
        self.assertTrue(self.contract_line.manual_renew_needed)

    def test_auto_renew_canceled_constrain(self):
        self.contract_line.cancel()
        with self.assertRaises(ValidationError):
            self.contract_line.write({"is_auto_renew": True})

    def test_auto_renew_allowed_constrain(self):
        self.contract_line.date_end = False
        with self.assertRaises(ValidationError):
            self.contract_line.write({"is_auto_renew": True})
