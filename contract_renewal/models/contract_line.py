# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ContractLine(models.Model):
    _inherit = "contract.line"

    manual_renew_needed = fields.Boolean(
        default=False,
        help="This flag is used to make a difference between a definitive stop"
        " and temporary one for which a user is not able to plan a"
        "renewal in advance",
    )
    state = fields.Selection(selection_add=[("to-renew", "To renew")])

    @api.depends(
        "is_auto_renew",
    )
    def _compute_is_stop_allowed(self):
        ret_vals = super()._compute_is_stop_allowed()

        # BEFORE
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "BEFORE"
            and not a.contract_id.is_terminated
            and not a.is_stop_allowed
            and not a.is_canceled
            and ((a.is_auto_renew and a.date_end) or (not a.is_auto_renew))
        ):
            line.is_stop_allowed = True

        # IN
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "IN"
            and not a.contract_id.is_terminated
            and not a.is_stop_allowed
            and not a.is_canceled
            and ((a.is_auto_renew and a.date_end) or (not a.is_auto_renew))
        ):
            line.is_stop_allowed = True

        for line in self.filtered(
            lambda a: a._get_allowed_when() == "AFTER"
            and not a.contract_id.is_terminated
            and a.is_stop_allowed
            and not a.is_canceled
            and a.date_end
            and not a.is_auto_renew
        ):
            line.is_stop_allowed = False
        return ret_vals

    @api.depends(
        "is_auto_renew",
    )
    def _compute_is_cancel_allowed(self):
        ret_vals = super()._compute_is_cancel_allowed()

        # BEFORE
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "BEFORE"
            and not a.contract_id.is_terminated
            and not a.is_cancel_allowed
            and not a.is_canceled
            and not a.last_date_invoiced
            and ((a.is_auto_renew and a.date_end) or not a.is_auto_renew)
        ):
            line.is_cancel_allowed = True
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "BEFORE"
            and not a.contract_id.is_terminated
            and a.is_cancel_allowed
            and not a.is_canceled
            and a.last_date_invoiced
            and ((a.is_auto_renew and a.date_end) or not a.is_auto_renew)
        ):
            line.is_cancel_allowed = False

        # IN
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "IN"
            and not a.contract_id.is_terminated
            and not a.is_cancel_allowed
            and not a.is_canceled
            and not a.last_date_invoiced
            and ((a.is_auto_renew and a.date_end) or not a.is_auto_renew)
        ):
            line.is_cancel_allowed = True
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "IN"
            and not a.contract_id.is_terminated
            and a.is_cancel_allowed
            and not a.is_canceled
            and a.last_date_invoiced
            and ((a.is_auto_renew and a.date_end) or not a.is_auto_renew)
        ):
            line.is_cancel_allowed = False

        # AFTER
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "AFTER"
            and not a.contract_id.is_terminated
            and a.is_cancel_allowed
            and not a.is_canceled
            and a.date_end
        ):
            line.is_cancel_allowed = False
        return ret_vals

    @api.depends(
        "is_auto_renew",
    )
    def _compute_is_uncancel_allowed(self):
        ret_vals = super()._compute_is_uncancel_allowed()
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "BEFORE"
            and not a.contract_id.is_terminated
            and a.is_uncancel_allowed
            and not a.is_canceled
            and ((a.is_auto_renew and a.date_end) or not a.is_auto_renew)
        ):
            line.is_uncancel_allowed = False
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "IN"
            and not a.contract_id.is_terminated
            and a.is_uncancel_allowed
            and not a.is_canceled
            and ((a.is_auto_renew and a.date_end) or not a.is_auto_renew)
        ):
            line.is_uncancel_allowed = False
        return ret_vals

    def _prepare_value_for_stop(self, date_end, **kwargs):
        vals = super()._prepare_value_for_stop(date_end, **kwargs)
        vals["is_auto_renew"] = False
        if kwargs.get("manual_renew_needed"):
            vals["manual_renew_needed"] = kwargs.get("manual_renew_needed")
        return vals

    def stop(self, date_end, post_message=True, **kwargs):
        for line in self.filtered(
            lambda a: date_end >= a.date_start and a.date_end and a.date_end <= date_end
        ):
            line.write(
                {
                    "is_auto_renew": False,
                    "manual_renew_needed": kwargs.get("manual_renew_needed", False),
                }
            )
        ret_vals = super().stop(date_end, post_message, **kwargs)
        return ret_vals

    @api.depends("is_auto_renew", "manual_renew_needed")
    def _compute_state(self):
        ret_val = super()._compute_state()
        today = fields.Date.context_today(self)
        for line in self.filtered(
            lambda a: not a.display_type and a.state not in ["canceled", "upcoming"]
        ):
            if (
                line.date_start
                and line.date_start <= today
                and (not line.date_end or line.date_end >= today)
            ):
                if (
                    line.termination_notice_date
                    and line.termination_notice_date < today
                    and not line.is_auto_renew
                    and not line.manual_renew_needed
                ):
                    line.state = "upcoming-close"
                else:
                    line.state = "in-progress"
                continue
            if line.date_end and line.date_end < today:
                # After
                if line.manual_renew_needed or line.is_auto_renew:
                    line.state = "to-renew"
                else:
                    line.state = "closed"
        return ret_val

    @api.model
    def _get_state_domain(self, state):
        today = fields.Date.context_today(self)
        domain = super()._get_state_domain(state)
        if state == "in-progress":
            return [
                "&",
                "&",
                "&",
                ("date_start", "<=", today),
                ("is_canceled", "=", False),
                "|",
                ("date_end", ">=", today),
                ("date_end", "=", False),
                "|",
                ("is_auto_renew", "=", True),
                "&",
                ("is_auto_renew", "=", False),
                ("termination_notice_date", ">", today),
            ]
        if state == "to-renew":
            return [
                "&",
                "&",
                ("is_canceled", "=", False),
                ("date_end", "<", today),
                "|",
                ("manual_renew_needed", "=", True),
                ("is_auto_renew", "=", True),
            ]
        if state == "upcoming-close":
            return [
                "&",
                "&",
                "&",
                "&",
                "&",
                ("date_start", "<=", today),
                ("is_auto_renew", "=", False),
                ("manual_renew_needed", "=", False),
                ("is_canceled", "=", False),
                ("termination_notice_date", "<", today),
                ("date_end", ">=", today),
            ]
        if state == "closed":
            return [
                ("is_canceled", "=", False),
                ("date_end", "<", today),
                ("is_auto_renew", "=", False),
            ]
        return domain

    def cancel(self):
        self.write({"is_auto_renew": False})
        ret_vals = super().cancel()
        return ret_vals

    @api.model
    def _get_first_date_end(
        self, date_start, auto_renew_rule_type, auto_renew_interval
    ):
        return (
            date_start
            + self.get_relative_delta(auto_renew_rule_type, auto_renew_interval)
            - relativedelta(days=1)
        )

    @api.onchange(
        "date_start",
        "is_auto_renew",
        "auto_renew_rule_type",
        "auto_renew_interval",
    )
    def _onchange_is_auto_renew(self):
        """Date end should be auto-computed if a contract line is set to
        auto_renew"""
        for line in self.filtered(lambda ln: ln.is_auto_renew and ln.date_start):
            line.date_end = self._get_first_date_end(
                line.date_start,
                line.auto_renew_rule_type,
                line.auto_renew_interval,
            )

    @api.constrains("is_canceled", "is_auto_renew")
    def _check_auto_renew_canceled_lines(self):
        if self.filtered(lambda ln: ln.is_canceled and ln.is_auto_renew):
            raise ValidationError(
                _("A canceled contract line can't be set to auto-renew")
            )

    @api.constrains("is_auto_renew", "date_end")
    def _check_allowed(self):
        if self.filtered(lambda a: a.is_auto_renew and not a.date_end):
            raise ValidationError(_("An auto-renew line must have a end date"))

    def _get_renewal_new_date_end(self):
        self.ensure_one()
        date_start = self.date_end + relativedelta(days=1)
        date_end = self._get_first_date_end(
            date_start, self.auto_renew_rule_type, self.auto_renew_interval
        )
        return date_end

    def _renew(self, date_end):
        self.ensure_one()
        self.date_end = date_end
        return self

    def renew(self):
        res = self.env["contract.line"]
        for line in self:
            date_end = line._get_renewal_new_date_end()
            date_start = line.date_end + relativedelta(days=1)
            new_line = line._renew(date_end)
            res |= new_line
            msg = Markup(
                _(
                    """Contract line for <b>%(product)s</b>
                renewed: <br/>
                - <strong>Start</strong>: %(new_date_start)s
                <br/>
                - <strong>End</strong>: %(new_date_end)s
                """
                )
            ) % {
                "product": line.name,
                "new_date_start": date_start,
                "new_date_end": date_end,
            }
            line.contract_id.message_post(body=msg)
        return res

    @api.model
    def _contract_line_to_renew_domain(self):
        return [
            ("contract_id.is_terminated", "=", False),
            ("is_auto_renew", "=", True),
            ("is_canceled", "=", False),
            ("termination_notice_date", "<=", fields.Date.context_today(self)),
        ]

    @api.model
    def cron_renew_contract_line(self):
        domain = self._contract_line_to_renew_domain()
        to_renew = self.search(domain)
        to_renew.renew()

    @api.model
    def _search_state(self, operator, value):
        states = [
            "upcoming",
            "in-progress",
            "to-renew",
            "upcoming-close",
            "closed",
            "canceled",
            False,
        ]
        if operator == "=":
            return self._get_state_domain(value)
        if operator == "!=":
            domain = []
            for state in states:
                if state != value:
                    if domain:
                        domain.insert(0, "|")
                    domain.extend(self._get_state_domain(state))
            return domain
        if operator == "in":
            domain = []
            for state in value:
                if domain:
                    domain.insert(0, "|")
                domain.extend(self._get_state_domain(state))
            return domain

        if operator == "not in":
            if set(value) == set(states):
                return [("id", "=", False)]
            return self._search_state(
                "in", [state for state in states if state not in value]
            )
