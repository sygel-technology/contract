# Copyright 2024 Manuel Regidor <manuel.regidor@sygel.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ContractLine(models.Model):
    _inherit = "contract.line"

    successor_contract_line_id = fields.Many2one(
        comodel_name="contract.line",
        string="Successor Contract Line",
        required=False,
        readonly=True,
        index=True,
        copy=False,
        help="In case of restart after suspension, this field contain the new "
        "contract line created.",
    )
    predecessor_contract_line_id = fields.Many2one(
        comodel_name="contract.line",
        string="Predecessor Contract Line",
        required=False,
        readonly=True,
        index=True,
        copy=False,
        help="Contract Line origin of this one.",
    )
    is_plan_successor_allowed = fields.Boolean(
        string="Plan successor allowed?", compute="_compute_is_plan_successor_allowed"
    )
    is_stop_plan_successor_allowed = fields.Boolean(
        string="Stop/Plan successor allowed?",
        compute="_compute_is_stop_plan_successor_allowed",
    )

    @api.depends(
        "successor_contract_line_id",
    )
    def _compute_is_stop_allowed(self):
        ret_vals = super()._compute_is_stop_allowed()

        # BEFORE
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "BEFORE"
            and not a.contract_id.is_terminated
            and not a.is_stop_allowed
            and not a.is_canceled
            and a.is_auto_renew
            and a.date_end
            and not a.successor_contract_line_id
        ):
            line.is_stop_allowed = True

        # IN
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "IN"
            and not a.contract_id.is_terminated
            and not a.is_stop_allowed
            and not a.is_canceled
            and (
                (a.is_auto_renew and a.date_end and not a.successor_contract_line_id)
                or (
                    not a.is_auto_renew
                    and (a.date_end or not a.successor_contract_line_id)
                )
            )
        ):
            line.is_stop_allowed = True

        # AFTER
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "AFTER"
            and not a.contract_id.is_terminated
            and not a.is_stop_allowed
            and not a.is_canceled
            and a.date_end
            and not a.successor_contract_line_id
        ):
            line.is_stop_allowed = True

        for line in self.filtered(
            lambda a: a._get_allowed_when() == "AFTER"
            and not a.contract_id.is_terminated
            and a.is_stop_allowed
            and not a.is_canceled
            and a.date_end
            and not a.is_auto_renew
            and a.successor_contract_line_id
        ):
            line.is_stop_allowed = False
        return ret_vals

    @api.depends(
        "successor_contract_line_id",
    )
    def _compute_is_cancel_allowed(self):
        ret_vals = super()._compute_is_cancel_allowed()
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "BEFORE"
            and not a.contract_id.is_terminated
            and not a.is_cancel_allowed
            and not a.is_canceled
            and not a.last_date_invoiced
            and a.is_auto_renew
            and a.date_end
            and not a.successor_contract_line_id
        ):
            line.is_cancel_allowed = True
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "BEFORE"
            and not a.contract_id.is_terminated
            and a.is_cancel_allowed
            and not a.is_canceled
            and a.last_date_invoiced
            and (
                (a.is_auto_renew and a.date_end and not a.successor_contract_line_id)
                or (
                    not a.is_auto_renew
                    and (a.date_end or (not a.successor_contract_line_id))
                )
            )
        ):
            line.is_cancel_allowed = False

        # IN
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "IN"
            and not a.contract_id.is_terminated
            and not a.is_cancel_allowed
            and not a.is_canceled
            and not a.last_date_invoiced
            and (
                (a.is_auto_renew and a.date_end and not a.successor_contract_line_id)
                or (
                    not a.is_auto_renew
                    and (a.date_end or not a.successor_contract_line_id)
                )
            )
        ):
            line.is_cancel_allowed = True

        for line in self.filtered(
            lambda a: a._get_allowed_when() == "IN"
            and not a.contract_id.is_terminated
            and a.is_cancel_allowed
            and not a.is_canceled
            and a.last_date_invoiced
            and (
                (a.is_auto_renew and a.date_end and not a.successor_contract_line_id)
                or (
                    not a.is_auto_renew
                    and (a.date_end or not a.successor_contract_line_id)
                )
            )
        ):
            line.is_cancel_allowed = False

        # AFTER
        for line in self.filtered(
            lambda a: a._get_allowed_when() == "AFTER"
            and not a.contract_id.is_terminated
            and a.is_cancel_allowed
            and not a.is_canceled
            and a.date_end
            and (not a.is_auto_renew or not a.successor_contract_line_id)
        ):
            line.is_cancel_allowed = False
        return ret_vals

    @api.depends(
        "is_auto_renew",
    )
    def _compute_is_un_cancel_allowed(self):
        ret_vals = super()._compute_is_un_cancel_allowed()
        for line in self.filtered(
            lambda a: a.is_un_cancel_allowed and a.predecessor_contract_line_id
        ):
            line.is_un_cancel_allowed = False
        return ret_vals

    @api.depends(
        "date_start",
        "date_end",
        "is_auto_renew",
        "successor_contract_line_id",
        "is_canceled",
        "contract_id.is_terminated",
    )
    def _compute_is_plan_successor_allowed(self):
        for line in self:
            plan_successor_allowed = False
            if not line.contract_id.is_terminated:
                when = line._get_allowed_when()
                # BEFORE
                if (
                    when == "BEFORE"
                    and not line.is_canceled
                    and not line.successor_contract_line_id
                    and not line.is_auto_renew
                    and line.date_end
                ):
                    plan_successor_allowed = True
                # IN
                elif (
                    when == "IN"
                    and not line.is_canceled
                    and not line.successor_contract_line_id
                    and not line.is_auto_renew
                    and line.date_end
                ):
                    plan_successor_allowed = True
                # AFTER
                elif (
                    when == "AFTER"
                    and not line.is_canceled
                    and line.date_end
                    and not line.is_auto_renew
                    and not line.successor_contract_line_id
                ):
                    plan_successor_allowed = True
            line.is_plan_successor_allowed = plan_successor_allowed

    @api.depends(
        "date_start",
        "date_end",
        "is_auto_renew",
        "successor_contract_line_id",
        "is_canceled",
        "contract_id.is_terminated",
    )
    def _compute_is_stop_plan_successor_allowed(self):
        for line in self:
            stop_plan_successor_allowed = False
            if not line.contract_id.is_terminated:
                when = line._get_allowed_when()

                # BEFORE
                if (
                    when == "BEFORE"
                    and not line.is_canceled
                    and not line.successor_contract_line_id
                    and (
                        (not line.is_auto_renew and line.date_end)
                        or (
                            not line.date_end
                            or (line.date_end and not line.last_date_invoiced)
                        )
                    )
                ):
                    stop_plan_successor_allowed = True

                # IN
                elif (
                    when == "IN"
                    and not line.is_canceled
                    and not line.successor_contract_line_id
                    and (
                        (line.is_auto_renew and line.date_end) or not line.is_auto_renew
                    )
                ):
                    stop_plan_successor_allowed = True
            line.is_stop_plan_successor_allowed = stop_plan_successor_allowed

    @api.depends("successor_contract_line_id")
    def _compute_state(self):
        ret_val = super()._compute_state()
        today = fields.Date.context_today(self)
        for line in self.filtered(
            lambda a: not a.display_type
            and a.date_end
            and a.date_end < today
            and not a.is_canceled
        ):
            if (
                line.manual_renew_needed
                and not line.successor_contract_line_id
                or line.is_auto_renew
            ):
                line.state = "to-renew"
            elif not line.is_auto_renew and (
                line.manual_renew_needed
                or (not (line.successor_contract_line_id or line.manual_renew_needed))
            ):
                line.state = "closed"
        return ret_val

    @api.model
    def _get_state_domain(self, state):
        today = fields.Date.context_today(self)
        domain = super()._get_state_domain(state)
        if state == "to-renew":
            return [
                "&",
                "&",
                ("is_canceled", "=", False),
                ("date_end", "<", today),
                "|",
                "&",
                ("manual_renew_needed", "=", True),
                ("successor_contract_line_id", "=", False),
                ("is_auto_renew", "=", True),
            ]
        if state == "closed":
            return [
                "&",
                "&",
                "&",
                ("is_canceled", "=", False),
                ("date_end", "<", today),
                ("is_auto_renew", "=", False),
                "|",
                "&",
                ("manual_renew_needed", "=", True),
                ("successor_contract_line_id", "!=", False),
                ("manual_renew_needed", "=", False),
            ]
        return domain

    @api.constrains("successor_contract_line_id", "is_auto_renew", "date_end")
    def _check_successors(self):
        """
        logical impossible combination:
            * a line with is_auto_renew True should have date_end and
              couldn't have successor_contract_line_id
            * a line without date_end can't have successor_contract_line_id

        """
        for rec in self:
            if rec.is_auto_renew and rec.successor_contract_line_id:
                logging.warning("_check_successors A")
                raise ValidationError(
                    _("A contract line with a successor " "can't be set to auto-renew")
                )
            elif not rec.date_end and rec.successor_contract_line_id:
                logging.warning("_check_successors B")
                raise ValidationError(
                    _("A contract line with a successor " "must have a end date")
                )

    @api.constrains("successor_contract_line_id", "date_end")
    def _check_overlap_successor(self):
        for rec in self:
            if rec.date_end and rec.successor_contract_line_id:
                if rec.date_end >= rec.successor_contract_line_id.date_start:
                    logging.warning("_check_overlap_successor")
                    raise ValidationError(
                        _("Contract line and its successor overlapped")
                    )

    @api.constrains("predecessor_contract_line_id", "date_start")
    def _check_overlap_predecessor(self):
        for rec in self:
            if (
                rec.predecessor_contract_line_id
                and rec.predecessor_contract_line_id.date_end
            ):
                if rec.date_start <= rec.predecessor_contract_line_id.date_end:
                    logging.warning("_check_overlap_predecessor")
                    raise ValidationError(
                        _("Contract line and its predecessor overlapped")
                    )

    def plan_successor(
        self,
        date_start,
        date_end,
        is_auto_renew,
        recurring_next_date=False,
        post_message=True,
    ):
        """
        Create a copy of a contract line in a new interval
        :param date_start: date_start for the successor_contract_line
        :param date_end: date_end for the successor_contract_line
        :param is_auto_renew: is_auto_renew option for successor_contract_line
        :param recurring_next_date: recurring_next_date for the
        successor_contract_line
        :return: successor_contract_line
        """
        contract_line = self.env["contract.line"]
        for rec in self:
            if not rec.is_plan_successor_allowed:
                raise ValidationError(_("Plan successor not allowed for this line"))
            rec.is_auto_renew = False
            new_line = self.create(
                rec._prepare_value_for_plan_successor(
                    date_start, date_end, is_auto_renew, recurring_next_date
                )
            )
            rec.successor_contract_line_id = new_line
            contract_line |= new_line
            if post_message:
                msg = _(
                    """Contract line for <strong>%(product)s</strong>
                    planned a successor: <br/>
                    - <strong>Start</strong>: %(new_date_start)s
                    <br/>
                    - <strong>End</strong>: %(new_date_end)s
                    """
                ) % {
                    "product": rec.name,
                    "new_date_start": new_line.date_start,
                    "new_date_end": new_line.date_end,
                }
                rec.contract_id.message_post(body=msg)
        return contract_line

    def stop_plan_successor(self, date_start, date_end, is_auto_renew):
        """
        Stop a contract line for a defined period and start it later
        Cases to consider:
            * contract line end's before the suspension period:
                -> apply stop
            * contract line start before the suspension period and end in it
                -> apply stop at suspension start date
                -> apply plan successor:
                    - date_start: suspension.date_end
                    - date_end: date_end    + (contract_line.date_end
                                            - suspension.date_start)
            * contract line start before the suspension period and end after it
                -> apply stop at suspension start date
                -> apply plan successor:
                    - date_start: suspension.date_end
                    - date_end: date_end + (suspension.date_end
                                        - suspension.date_start)
            * contract line start and end's in the suspension period
                -> apply delay
                    - delay: suspension.date_end - contract_line.date_start
            * contract line start in the suspension period and end after it
                -> apply delay
                    - delay: suspension.date_end - contract_line.date_start
            * contract line start  and end after the suspension period
                -> apply delay
                    - delay: suspension.date_end - suspension.start_date
        :param date_start: suspension start date
        :param date_end: suspension end date
        :param is_auto_renew: is the new line is set to auto_renew
        :return: created contract line
        """
        if not all(self.mapped("is_stop_plan_successor_allowed")):
            logging.warning("stop_plan_successor")
            raise ValidationError(_("Stop/Plan successor not allowed for this line"))
        contract_line = self.env["contract.line"]
        for rec in self:
            if rec.date_start >= date_start:
                if rec.date_start < date_end:
                    delay = (date_end - rec.date_start) + timedelta(days=1)
                else:
                    delay = (date_end - date_start) + timedelta(days=1)
                rec._delay(delay)
                contract_line |= rec
            else:
                if rec.date_end and rec.date_end < date_start:
                    rec.stop(date_start, post_message=False)
                elif (
                    rec.date_end
                    and rec.date_end > date_start
                    and rec.date_end < date_end
                ):
                    new_date_start = date_end + relativedelta(days=1)
                    new_date_end = (
                        date_end + (rec.date_end - date_start) + relativedelta(days=1)
                    )
                    rec.stop(
                        date_start - relativedelta(days=1),
                        post_message=False,
                        **{"manual_renew_needed": True},
                    )
                    contract_line |= rec.plan_successor(
                        new_date_start,
                        new_date_end,
                        is_auto_renew,
                        post_message=False,
                    )
                else:
                    new_date_start = date_end + relativedelta(days=1)
                    if rec.date_end:
                        new_date_end = (
                            rec.date_end
                            + (date_end - date_start)
                            + relativedelta(days=1)
                        )
                    else:
                        new_date_end = rec.date_end
                    rec.stop(
                        date_start - relativedelta(days=1),
                        post_message=False,
                        **{"manual_renew_needed": True},
                    )
                    contract_line |= rec.plan_successor(
                        new_date_start,
                        new_date_end,
                        is_auto_renew,
                        post_message=False,
                    )
            msg = Markup(
                _(
                    """Contract line for <strong>%(product)s</strong>
                suspended: <br/>
                - <strong>Suspension Start</strong>: %(new_date_start)s
                <br/>
                - <strong>Suspension End</strong>: %(new_date_end)s
                """
                )
            ) % {
                "product": rec.name,
                "new_date_start": date_start,
                "new_date_end": date_end,
            }
            rec.contract_id.message_post(body=msg)
        return contract_line

    def cancel(self):
        ret_vals = super().cancel()
        self.mapped("predecessor_contract_line_id").write(
            {"successor_contract_line_id": False}
        )
        return ret_vals

    def _prepare_value_for_plan_successor(
        self, date_start, date_end, is_auto_renew, recurring_next_date=False
    ):
        self.ensure_one()
        if not recurring_next_date:
            recurring_next_date = self.get_next_invoice_date(
                date_start,
                self.recurring_invoicing_type,
                self.recurring_invoicing_offset,
                self.recurring_rule_type,
                self.recurring_interval,
                max_date_end=date_end,
            )
        logging.warning("date_end")
        logging.warning(date_end)
        new_vals = self.read()[0]
        new_vals.pop("id", None)
        new_vals.pop("last_date_invoiced", None)
        values = self._convert_to_write(new_vals)
        values["date_start"] = date_start
        values["date_end"] = date_end
        values["recurring_next_date"] = recurring_next_date
        values["is_auto_renew"] = is_auto_renew
        values["predecessor_contract_line_id"] = self.id
        return values

    def uncancel(self, recurring_next_date):
        ret_vals = super().uncancel(recurring_next_date)
        for line in self.filtered("predecessor_contract_line_id"):
            predecessor_contract_line = line.predecessor_contract_line_id
            assert not predecessor_contract_line.successor_contract_line_id
            predecessor_contract_line.successor_contract_line_id = line
        return ret_vals

    def action_plan_successor(self):
        self.ensure_one()
        context = {
            "default_contract_line_id": self.id,
            "default_is_auto_renew": self.is_auto_renew,
        }
        context.update(self.env.context)
        view_id = self.env.ref(
            "contract_line_successor.contract_line_wizard_plan_successor_form_view"
        ).id
        return {
            "type": "ir.actions.act_window",
            "name": "Plan contract line successor",
            "res_model": "contract.line.wizard",
            "view_mode": "form",
            "views": [(view_id, "form")],
            "target": "new",
            "context": context,
        }

    def action_stop_plan_successor(self):
        self.ensure_one()
        context = {
            "default_contract_line_id": self.id,
            "default_is_auto_renew": self.is_auto_renew,
        }
        context.update(self.env.context)
        view_id = self.env.ref(
            "contract_line_successor.contract_line_wizard_stop_plan_successor_form_view"
        ).id
        return {
            "type": "ir.actions.act_window",
            "name": "Suspend contract line",
            "res_model": "contract.line.wizard",
            "view_mode": "form",
            "views": [(view_id, "form")],
            "target": "new",
            "context": context,
        }

    def _renew_create_line(self, date_end):
        self.ensure_one()
        date_start = self.date_end + relativedelta(days=1)
        is_auto_renew = self.is_auto_renew
        self.stop(self.date_end, post_message=False)
        new_line = self.plan_successor(
            date_start, date_end, is_auto_renew, post_message=False
        )
        return new_line

    def _renew(self, date_end):
        self.ensure_one()
        company = self.contract_id.company_id
        if company.create_new_line_at_contract_line_renew:
            new_line = self._renew_create_line(date_end)
        else:
            new_line = super()._renew(date_end)
        return new_line
