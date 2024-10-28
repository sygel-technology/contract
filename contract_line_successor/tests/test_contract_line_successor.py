# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError

from odoo.addons.contract_renewal.tests.test_contract_renewal import TestContractRenewal


class TestContractLineRelation(TestContractRenewal):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass()
        cls.contract_line = cls.contract.contract_line_ids[0]
        cls.contract_line_states = [
            state[0] for state in cls.env["contract.line"]._fields["state"].selection
        ]

    def test_to_renew_state_successor(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        self.contract_line.is_auto_renew = True
        self.assertEqual(self.contract_line.state, "to-renew")
        self.contract_line.is_auto_renew = False
        self.contract_line.manual_renew_needed = True
        self.assertTrue(
            self.contract_line.search(
                [("id", "=", self.contract_line.id), ("state", "=", "to-renew")]
            )
        )
        self.assertFalse(self.contract_line.successor_contract_line_id)
        self.assertEqual(self.contract_line.state, "to-renew")

    def test_closed_state_successor(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        self.contract_line.is_auto_renew = False
        self.contract_line.manual_renew_needed = False
        self.assertTrue(
            self.contract_line.search(
                [("id", "=", self.contract_line.id), ("state", "=", "closed")]
            )
        )
        self.assertEqual(self.contract_line.state, "closed")
        self.contract_line.manual_renew_needed = True
        self.contract_line.plan_successor(
            fields.Date.today(),
            fields.Date.today() + relativedelta(years=1),
            self.contract_line.is_auto_renew,
        )
        self.assertFalse(self.contract_line.is_canceled)
        self.assertTrue(self.contract_line.date_end < fields.Date.today())
        self.assertFalse(self.contract_line.is_auto_renew)
        self.assertTrue(self.contract_line.manual_renew_needed)
        self.assertTrue(self.contract_line.successor_contract_line_id)
        self.assertEqual(self.contract_line.state, "closed")
        self.assertTrue(
            self.contract_line.search(
                [("id", "=", self.contract_line.id), ("state", "=", "closed")]
            )
        )

    def test_plan_successor(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=1)
        wizard = self.env["contract.line.wizard"].create(
            {
                "contract_line_id": self.contract_line.id,
                "is_auto_renew": self.contract_line.is_auto_renew,
                "date_start": self.contract_line.date_end + relativedelta(days=1),
                "date_end": self.contract_line.date_end + relativedelta(years=1),
            }
        )
        wizard.plan_successor()
        successor_line = self.contract_line.successor_contract_line_id
        self.assertTrue(successor_line)
        self.assertEqual(successor_line.state, "upcoming")
        self.assertEqual(
            successor_line.date_start,
            self.contract_line.date_end + relativedelta(days=1),
        )
        self.assertEqual(
            successor_line.date_end,
            self.contract_line.date_end + relativedelta(years=1),
        )

    def test_stop_successor(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(years=1)
        self.contract_line.is_auto_renew = True
        suspension_date_start = fields.Date.today() + relativedelta(months=2)
        wizard = self.env["contract.line.wizard"].create(
            {
                "contract_line_id": self.contract_line.id,
                "date_start": suspension_date_start,
                "date_end": suspension_date_start + relativedelta(days=30),
                "is_auto_renew": self.contract_line.is_auto_renew,
            }
        )
        wizard.stop_plan_successor()
        successor_line = self.contract_line.successor_contract_line_id
        self.assertTrue(successor_line)
        self.assertEqual(successor_line.state, "upcoming")
        self.assertEqual(
            self.contract_line.date_end,
            fields.Date.today() + relativedelta(months=2) + relativedelta(days=-1),
        )
        self.assertEqual(
            successor_line.date_start, fields.Date.today() + relativedelta(months=3)
        )
        self.assertEqual(
            successor_line.date_end,
            fields.Date.today() + relativedelta(years=1) + relativedelta(days=31),
        )

    def test_check_plan_successor(self):
        with self.assertRaises(ValidationError):
            self.acct_line.plan_successor(
                fields.Date.to_date("2016-03-01"),
                fields.Date.to_date("2018-09-01"),
                False,
            )

    def test_check_successors(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        self.contract_line.is_auto_renew = False
        self.contract_line.manual_renew_needed = True
        self.contract_line.plan_successor(
            fields.Date.today(),
            fields.Date.today() + relativedelta(years=1),
            self.contract_line.is_auto_renew,
        )
        with self.assertRaises(ValidationError):
            self.contract_line.is_auto_renew = True
        with self.assertRaises(ValidationError):
            self.contract_line.date_end = False

    def test_check_overlap_successor(self):
        self.contract_line.date_end = fields.Date.today() + relativedelta(days=-1)
        self.contract_line.is_auto_renew = False
        self.contract_line.manual_renew_needed = True
        successor = self.contract_line.plan_successor(
            fields.Date.today(),
            fields.Date.today() + relativedelta(years=1),
            self.contract_line.is_auto_renew,
        )
        logging.warning(successor.date_start)
        with self.assertRaises(ValidationError):
            self.contract_line.date_end = successor.date_start + relativedelta(days=1)
