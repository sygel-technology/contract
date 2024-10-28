# Copyright 2017 LasLabs Inc.
# Copyright 2018 ACSONE SA/NV.
# Copyright 2020 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Date


class ContractLine(models.Model):
    _name = "contract.line"
    _description = "Contract Line"
    _inherit = [
        "contract.abstract.contract.line",
        "contract.recurrency.mixin",
        "analytic.mixin",
    ]
    _order = "sequence,id"

    sequence = fields.Integer()
    contract_id = fields.Many2one(
        comodel_name="contract.contract",
        string="Contract",
        required=True,
        index=True,
        auto_join=True,
        ondelete="cascade",
    )
    currency_id = fields.Many2one(related="contract_id.currency_id")
    date_start = fields.Date(required=True)
    date_end = fields.Date(compute="_compute_date_end", store=True, readonly=False)
    termination_notice_date = fields.Date(
        compute="_compute_termination_notice_date",
        store=True,
        copy=False,
    )
    create_invoice_visibility = fields.Boolean(
        compute="_compute_create_invoice_visibility"
    )
    is_stop_allowed = fields.Boolean(
        string="Stop allowed?", compute="_compute_is_stop_allowed"
    )
    is_cancel_allowed = fields.Boolean(
        string="Cancel allowed?", compute="_compute_is_cancel_allowed"
    )
    is_un_cancel_allowed = fields.Boolean(
        string="Un-Cancel allowed?", compute="_compute_is_un_cancel_allowed"
    )
    state = fields.Selection(
        selection=[
            ("upcoming", "Upcoming"),
            ("in-progress", "In-progress"),
            ("upcoming-close", "Upcoming Close"),
            ("closed", "Closed"),
            ("canceled", "Canceled"),
        ],
        compute="_compute_state",
        search="_search_state",
    )
    active = fields.Boolean(
        string="Active",
        related="contract_id.active",
        store=True,
        readonly=True,
    )

    @api.depends(
        "last_date_invoiced",
        "date_start",
        "date_end",
        "contract_id.last_date_invoiced",
        "contract_id.contract_line_ids.last_date_invoiced",
    )
    def _compute_next_period_date_start(self):
        """Rectify next period date start if another line in the contract has been
        already invoiced previously when the recurrence is by contract.
        """
        rest = self.filtered(lambda x: x.contract_id.line_recurrence)
        for rec in self - rest:
            lines = rec.contract_id.contract_line_ids
            if not rec.last_date_invoiced and any(lines.mapped("last_date_invoiced")):
                next_period_date_start = max(
                    lines.filtered("last_date_invoiced").mapped("last_date_invoiced")
                ) + relativedelta(days=1)
                if rec.date_end and next_period_date_start > rec.date_end:
                    next_period_date_start = False
                rec.next_period_date_start = next_period_date_start
            else:
                rest |= rec
        return super(ContractLine, rest)._compute_next_period_date_start()

    @api.depends("contract_id.date_end", "contract_id.line_recurrence")
    def _compute_date_end(self):
        self._set_recurrence_field("date_end")

    @api.depends(
        "date_end",
        "termination_notice_rule_type",
        "termination_notice_interval",
    )
    def _compute_termination_notice_date(self):
        for rec in self:
            if rec.date_end:
                rec.termination_notice_date = rec.date_end - self.get_relative_delta(
                    rec.termination_notice_rule_type,
                    rec.termination_notice_interval,
                )
            else:
                rec.termination_notice_date = False

    @api.depends(
        "is_canceled",
        "date_start",
        "date_end",
        "termination_notice_date",
    )
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.state = False
            if rec.display_type:
                continue
            if rec.is_canceled:
                rec.state = "canceled"
                continue

            if rec.date_start and rec.date_start > today:
                # Before period
                rec.state = "upcoming"
                continue
            if (
                rec.date_start
                and rec.date_start <= today
                and (not rec.date_end or rec.date_end >= today)
            ):
                # In period
                if rec.termination_notice_date and rec.termination_notice_date < today:
                    rec.state = "upcoming-close"
                else:
                    rec.state = "in-progress"
                continue
            if rec.date_end and rec.date_end < today:
                # After
                rec.state = "closed"

    @api.model
    def _get_state_domain(self, state):
        today = fields.Date.context_today(self)
        if state == "upcoming":
            return [
                "&",
                ("date_start", ">", today),
                ("is_canceled", "=", False),
            ]
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
                ("termination_notice_date", ">", today),
            ]
        if state == "upcoming-close":
            return [
                "&",
                "&",
                "&",
                ("date_start", "<=", today),
                ("is_canceled", "=", False),
                ("termination_notice_date", "<", today),
                ("date_end", ">=", today),
            ]
        if state == "closed":
            return [
                "&",
                ("is_canceled", "=", False),
                ("date_end", "<", today),
            ]
        if state == "canceled":
            return [("is_canceled", "=", True)]
        if not state:
            return [("display_type", "!=", False)]

    @api.model
    def _search_state(self, operator, value):
        states = [
            "upcoming",
            "in-progress",
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

    def _get_allowed_when(self):
        self.ensure_one()
        today = Date.today()
        if self.date_start and today < self.date_start:
            return "BEFORE"
        if self.date_end and today > self.date_end:
            return "AFTER"
        return "IN"

    @api.depends(
        "date_start",
        "date_end",
        "last_date_invoiced",
        "is_canceled",
        "contract_id.is_terminated",
    )
    def _compute_is_stop_allowed(self):
        for line in self:
            is_stop_allowed = False
            if not line.contract_id.is_terminated:
                when = line._get_allowed_when()
                if when == "BEFORE" and not (
                    line.last_date_invoiced and line.is_canceled
                ):
                    is_stop_allowed = True
                elif when == "AFTER":
                    is_stop_allowed = True
                elif when == "IN" and not line.is_canceled:
                    is_stop_allowed = True
            line.is_stop_allowed = is_stop_allowed

    @api.depends(
        "date_start",
        "date_end",
        "last_date_invoiced",
        "is_canceled",
        "contract_id.is_terminated",
    )
    def _compute_is_cancel_allowed(self):
        for line in self:
            is_cancel_allowed = False
            if not (
                line.contract_id.is_terminated
                or line.is_canceled
                or line.last_date_invoiced
            ):
                when = line._get_allowed_when()
                if when in ["BEFORE", "IN"]:
                    is_cancel_allowed = True
            line.is_cancel_allowed = is_cancel_allowed

    @api.depends(
        "is_stop_allowed",
        "is_cancel_allowed",
        "is_canceled",
        "contract_id.is_terminated",
    )
    def _compute_is_un_cancel_allowed(self):
        for line in self:
            is_un_cancel_allowed = False
            if (
                not (
                    line.contract_id.is_terminated
                    or line.is_stop_allowed
                    or line.is_cancel_allowed
                )
                and line.is_canceled
            ):
                is_un_cancel_allowed = True
            line.is_un_cancel_allowed = is_un_cancel_allowed

    @api.model
    def _compute_first_recurring_next_date(
        self,
        date_start,
        recurring_invoicing_type,
        recurring_rule_type,
        recurring_interval,
    ):
        # deprecated method for backward compatibility
        return self.get_next_invoice_date(
            date_start,
            recurring_invoicing_type,
            self._get_default_recurring_invoicing_offset(
                recurring_invoicing_type, recurring_rule_type
            ),
            recurring_rule_type,
            recurring_interval,
            max_date_end=False,
        )

    @api.constrains("recurring_next_date", "date_start")
    def _check_recurring_next_date_start_date(self):
        for line in self:
            if line.display_type == "line_section" or not line.recurring_next_date:
                continue
            if line.date_start and line.recurring_next_date:
                if line.date_start > line.recurring_next_date:
                    raise ValidationError(
                        _(
                            "You can't have a date of next invoice anterior "
                            "to the start of the contract line '%s'"
                        )
                        % line.name
                    )

    @api.constrains(
        "date_start", "date_end", "last_date_invoiced", "recurring_next_date"
    )
    def _check_last_date_invoiced(self):
        for rec in self.filtered("last_date_invoiced"):
            if rec.date_end and rec.date_end < rec.last_date_invoiced:
                raise ValidationError(
                    _(
                        "You can't have the end date before the date of last "
                        "invoice for the contract line '%s'"
                    )
                    % rec.name
                )
            if not rec.contract_id.line_recurrence:
                continue
            if rec.date_start and rec.date_start > rec.last_date_invoiced:
                raise ValidationError(
                    _(
                        "You can't have the start date after the date of last "
                        "invoice for the contract line '%s'"
                    )
                    % rec.name
                )
            if (
                rec.recurring_next_date
                and rec.recurring_next_date <= rec.last_date_invoiced
            ):
                raise ValidationError(
                    _(
                        "You can't have the next invoice date before the date "
                        "of last invoice for the contract line '%s'"
                    )
                    % rec.name
                )

    @api.constrains("recurring_next_date")
    def _check_recurring_next_date_recurring_invoices(self):
        for rec in self:
            if not rec.recurring_next_date and (
                not rec.date_end
                or not rec.last_date_invoiced
                or rec.last_date_invoiced < rec.date_end
            ):
                raise ValidationError(
                    _(
                        "You must supply a date of next invoice for contract "
                        "line '%s'"
                    )
                    % rec.name
                )

    @api.constrains("date_start", "date_end")
    def _check_start_end_dates(self):
        for line in self.filtered("date_end"):
            if line.date_start and line.date_end:
                if line.date_start > line.date_end:
                    raise ValidationError(
                        _(
                            "Contract line '%s' start date can't be later than"
                            " end date"
                        )
                        % line.name
                    )

    @api.depends(
        "display_type",
        "is_recurring_note",
        "recurring_next_date",
        "date_start",
        "date_end",
    )
    def _compute_create_invoice_visibility(self):
        # TODO: depending on the lines, and their order, some sections
        # have no meaning in certain invoices
        today = fields.Date.context_today(self)
        for rec in self:
            if (
                (not rec.display_type or rec.is_recurring_note)
                and rec.date_start
                and today >= rec.date_start
            ):
                rec.create_invoice_visibility = bool(rec.recurring_next_date)
            else:
                rec.create_invoice_visibility = False

    def _prepare_invoice_line(self):
        self.ensure_one()
        dates = self._get_period_to_invoice(
            self.last_date_invoiced, self.recurring_next_date
        )
        name = self._insert_markers(dates[0], dates[1])
        return {
            "quantity": self._get_quantity_to_invoice(*dates),
            "product_uom_id": self.uom_id.id,
            "discount": self.discount,
            "contract_line_id": self.id,
            "analytic_distribution": self.analytic_distribution,
            "sequence": self.sequence,
            "name": name,
            "price_unit": self.price_unit,
            "display_type": self.display_type or "product",
            "product_id": self.product_id.id,
        }

    def _get_period_to_invoice(
        self, last_date_invoiced, recurring_next_date, stop_at_date_end=True
    ):
        # TODO this method can now be removed, since
        # TODO self.next_period_date_start/end have the same values
        self.ensure_one()
        if not recurring_next_date:
            return False, False, False
        first_date_invoiced = (
            last_date_invoiced + relativedelta(days=1)
            if last_date_invoiced
            else self.date_start
        )
        last_date_invoiced = self.get_next_period_date_end(
            first_date_invoiced,
            self.recurring_rule_type,
            self.recurring_interval,
            max_date_end=(self.date_end if stop_at_date_end else False),
            next_invoice_date=recurring_next_date,
            recurring_invoicing_type=self.recurring_invoicing_type,
            recurring_invoicing_offset=self.recurring_invoicing_offset,
        )
        return first_date_invoiced, last_date_invoiced, recurring_next_date

    def _insert_markers(self, first_date_invoiced, last_date_invoiced):
        self.ensure_one()
        lang_obj = self.env["res.lang"]
        lang = lang_obj.search([("code", "=", self.contract_id.partner_id.lang)])
        date_format = lang.date_format or "%m/%d/%Y"
        name = self.name
        name = name.replace("#START#", first_date_invoiced.strftime(date_format))
        name = name.replace("#END#", last_date_invoiced.strftime(date_format))
        return name

    def _update_recurring_next_date(self):
        # FIXME: Change method name according to real updated field
        # e.g.: _update_last_date_invoiced()
        for rec in self:
            last_date_invoiced = rec.next_period_date_end
            rec.write(
                {
                    "last_date_invoiced": last_date_invoiced,
                }
            )

    def _delay(self, delay_delta):
        """
        Delay a contract line
        :param delay_delta: delay relative delta
        :return: delayed contract line
        """
        for rec in self:
            if rec.last_date_invoiced:
                raise ValidationError(
                    _("You can't delay a contract line " "invoiced at least one time.")
                )
            new_date_start = rec.date_start + delay_delta
            if rec.date_end:
                new_date_end = rec.date_end + delay_delta
            else:
                new_date_end = False
            new_recurring_next_date = self.get_next_invoice_date(
                new_date_start,
                rec.recurring_invoicing_type,
                rec.recurring_invoicing_offset,
                rec.recurring_rule_type,
                rec.recurring_interval,
                max_date_end=new_date_end,
            )
            rec.write(
                {
                    "date_start": new_date_start,
                    "date_end": new_date_end,
                    "recurring_next_date": new_recurring_next_date,
                }
            )

    def _prepare_value_for_stop(self, date_end, **kwargs):
        self.ensure_one()
        return {
            "date_end": date_end,
            "recurring_next_date": self.get_next_invoice_date(
                self.next_period_date_start,
                self.recurring_invoicing_type,
                self.recurring_invoicing_offset,
                self.recurring_rule_type,
                self.recurring_interval,
                max_date_end=date_end,
            ),
        }

    def stop(self, date_end, post_message=True, **kwargs):
        """
        Put date_end on contract line
        We don't consider contract lines that end's before the new end date
        :param date_end: new date end for contract line
        :return: True
        """
        if not all(self.mapped("is_stop_allowed")):
            raise ValidationError(_("Stop not allowed for this line"))
        for rec in self:
            if date_end < rec.date_start:
                rec.cancel()
            else:
                if not rec.date_end or rec.date_end > date_end:
                    old_date_end = rec.date_end
                    rec.write(rec._prepare_value_for_stop(date_end, **kwargs))
                    if post_message:
                        msg = Markup(
                            _(
                                """Contract line for <strong>%(product)s</strong>
                            stopped: <br/>
                            - <strong>End</strong>: %(old_end)s -- %(new_end)s
                            """
                            )
                        ) % {
                            "product": rec.name,
                            "old_end": old_date_end,
                            "new_end": rec.date_end,
                        }
                        rec.contract_id.message_post(body=msg)
        return True

    def cancel(self):
        if not all(self.mapped("is_cancel_allowed")):
            raise ValidationError(_("Cancel not allowed for this line"))
        for contract in self.mapped("contract_id"):
            lines = self.filtered(lambda line, c=contract: line.contract_id == c)
            msg = _(
                "Contract line canceled: %s",
                "<br/>- ".join(
                    [f"<strong>{name}</strong>" for name in lines.mapped("name")]
                ),
            )
            contract.message_post(body=msg)
        return self.write({"is_canceled": True})

    def uncancel(self, recurring_next_date):
        if not all(self.mapped("is_un_cancel_allowed")):
            raise ValidationError(_("Un-cancel not allowed for this line"))
        for contract in self.mapped("contract_id"):
            lines = self.filtered(lambda line, c=contract: line.contract_id == c)
            msg = _(
                "Contract line Un-canceled: %s",
                "<br/>- ".join(
                    [f"<strong>{name}</strong>" for name in lines.mapped("name")]
                ),
            )
            contract.message_post(body=msg)
        for rec in self:
            rec.is_canceled = False
            rec.recurring_next_date = recurring_next_date
        return True

    def action_uncancel(self):
        self.ensure_one()
        context = {
            "default_contract_line_id": self.id,
            "default_recurring_next_date": fields.Date.context_today(self),
        }
        context.update(self.env.context)
        view_id = self.env.ref("contract.contract_line_wizard_uncancel_form_view").id
        return {
            "type": "ir.actions.act_window",
            "name": "Un-Cancel Contract Line",
            "res_model": "contract.line.wizard",
            "view_mode": "form",
            "views": [(view_id, "form")],
            "target": "new",
            "context": context,
        }

    def action_stop(self):
        self.ensure_one()
        context = {
            "default_contract_line_id": self.id,
            "default_date_end": self.date_end,
        }
        context.update(self.env.context)
        view_id = self.env.ref("contract.contract_line_wizard_stop_form_view").id
        return {
            "type": "ir.actions.act_window",
            "name": "Terminate contract line",
            "res_model": "contract.line.wizard",
            "view_mode": "form",
            "views": [(view_id, "form")],
            "target": "new",
            "context": context,
        }

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        default_contract_type = self.env.context.get("default_contract_type")
        if view_type == "tree" and default_contract_type == "purchase":
            view_id = self.env.ref("contract.contract_line_supplier_tree_view").id
        if view_type == "form":
            if default_contract_type == "purchase":
                view_id = self.env.ref("contract.contract_line_supplier_form_view").id
            elif default_contract_type == "sale":
                view_id = self.env.ref("contract.contract_line_customer_form_view").id
        return super().get_view(view_id, view_type, **options)

    def unlink(self):
        """stop unlink uncnacled lines"""
        for record in self:
            if not (record.is_canceled or record.display_type):
                raise ValidationError(_("Contract line must be canceled before delete"))
        return super().unlink()

    def _get_quantity_to_invoice(
        self, period_first_date, period_last_date, invoice_date
    ):
        self.ensure_one()
        return self.quantity if not self.display_type else 0.0
