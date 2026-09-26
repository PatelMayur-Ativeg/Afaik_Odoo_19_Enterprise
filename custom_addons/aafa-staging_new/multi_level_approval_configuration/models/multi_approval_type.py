##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################
# Libs for safe_eval
import logging

from lxml import etree
from lxml.builder import E

from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import config
from odoo.tools.safe_eval import safe_eval, test_python_expr

_logger = logging.getLogger(__name__)


class MultiApprovalType(models.Model):
    _inherit = "multi.approval.type"
    _order = "priority"

    apply_for_model = fields.Boolean("Apply for Model?")
    is_configured = fields.Boolean("Configured?", copy=False)
    submit_python_code = fields.Text("Submit for Approval Action")
    approve_python_code = fields.Text("Approved Action")
    refuse_python_code = fields.Text("Refused Action")

    domain = fields.Text(default="[]")
    model_id = fields.Selection(selection="_list_all_models", string="Model")
    is_free_create = fields.Boolean("Free Create?")
    hide_button = fields.Boolean("Hide Buttons from Model View?")
    state_field_id = fields.Many2one("ir.model.fields", string="State / Stage Field")
    constraint_field_ids = fields.Many2many(
        "ir.model.fields",
        string="Constraint Fields",
        help="Prevent updating these field if the document is needed approval",
    )
    constraint_field_names = fields.Serialized(
        compute="_compute_constraint_field_names", store=True
    )
    constraint_field_approved_ids = fields.Many2many(
        "ir.model.fields",
        "multi_approval_type_field_rel",
        string="Readonly Fields",
        help="Prevent updating these field if the document has been approved",
    )
    constraint_field_names_approved = fields.Serialized(
        compute="_compute_constraint_field_names_approved", store=True
    )
    company_id = fields.Many2one(comodel_name="res.company", string="Company")
    group_ids = fields.Many2many(
        "res.groups", "ma_type_group_rel", "ma_type_id", "group_id", string="Groups"
    )
    bypass_approval_user_ids = fields.Many2many(
        "res.users",
        "ma_type_user_rel",
        "ma_type_id",
        "user_id",
        string="Bypass Approval Users",
    )

    is_global = fields.Boolean(compute="_compute_global", store=True)
    priority = fields.Integer(default=100)
    next_move_ids = fields.Many2many(
        "multi.approval.type", "multi_approval_type_next_move", "type_id", "next_id"
    )
    next_move_policy = fields.Selection(
        [("auto", "Automatically"), ("manu", "Manually")], default="auto"
    )
    auto_request = fields.Boolean(default=False)
    auto_request_follower_python_code = fields.Text()
    auto_request_partner_ids = fields.Many2many(
        "res.partner", "partner_approval_type_rel", "type_id", "partner_id"
    )

    @api.depends("state_field_id", "constraint_field_ids")
    def _compute_constraint_field_names(self):
        for record in self:
            all_fields = record.state_field_id | record.constraint_field_ids
            record.constraint_field_names = {
                fname: 1 for fname in all_fields.mapped("name")
            }

    @api.depends("constraint_field_approved_ids")
    def _compute_constraint_field_names_approved(self):
        for record in self:
            all_fields = record.constraint_field_approved_ids
            record.constraint_field_names_approved = {
                fname: 1 for fname in all_fields.mapped("name")
            }

    @api.model
    def _get_default_description(self):
        return """
Hi,
<br/> <br/>
Please review my request.<br/>
Click
<a target="__blank__" href="{record_url}">
{record.display_name}
</a> to view more !
<br/> <br/>
Thanks,
        """

    request_tmpl = fields.Html(default=_get_default_description)

    @api.constrains(
        "submit_python_code",
        "approve_python_code",
        "refuse_python_code",
        "auto_request_follower_python_code",
    )
    def _check_python_code(self):
        for rec in self.sudo().filtered("submit_python_code"):
            try:
                msg = test_python_expr(expr=rec.submit_python_code.strip(), mode="exec")
            except Exception as exc:
                raise ValidationError(self.env._("Invalid python syntax")) from exc
            if msg:
                raise ValidationError(msg)
        for rec in self.sudo().filtered("approve_python_code"):
            try:
                msg = test_python_expr(
                    expr=rec.approve_python_code.strip(), mode="exec"
                )
            except Exception as exc:
                raise ValidationError(self.env._("Invalid python syntax")) from exc
            if msg:
                raise ValidationError(msg)
        for rec in self.sudo().filtered("refuse_python_code"):
            try:
                msg = test_python_expr(expr=rec.refuse_python_code.strip(), mode="exec")
            except Exception as exc:
                raise ValidationError(self.env._("Invalid python syntax")) from exc
            if msg:
                raise ValidationError(msg)
        for rec in self.sudo().filtered("auto_request_follower_python_code"):
            try:
                msg = test_python_expr(
                    expr=rec.auto_request_follower_python_code.strip(), mode="exec"
                )
            except Exception as exc:
                raise ValidationError(self.env._("Invalid python syntax")) from exc
            if msg:
                raise ValidationError(msg)

    @api.depends("group_ids")
    def _compute_global(self):
        for rule in self:
            rule.is_global = not rule.group_ids

    @api.model
    def _get_types(self, model_name):
        type_ids = self._fetch_types(model_name)
        res = self.browse(type_ids)
        return res

    @api.model
    @tools.conditional(
        "xml" not in config["dev_mode"],
        tools.ormcache(
            "self.env.uid", "self.env.company.id", "self.env.su", "model_name"
        ),
    )
    def _fetch_types(self, model_name):
        """
        Returns all the types matching the model
        """
        # if self.env.su:
        #    return self.browse(())
        query = """
            SELECT t.id FROM multi_approval_type t
            WHERE t.model_id=%s
                AND t.active
                AND t.is_configured
                AND (t.id IN (
                        SELECT ma_type_id
                        FROM ma_type_group_rel mg
                        JOIN res_groups_users_rel gu
                            ON (mg.group_id=gu.gid)
                        WHERE gu.uid=%s)
                    OR t.is_global)
                AND (t.company_id ISNULL
                    OR t.company_id=%s)
                AND t.id NOT IN (
                    SELECT ma_type_id
                    FROM ma_type_user_rel bu
                    WHERE bu.user_id = %s
                )
            ORDER BY t.priority, t.id
        """

        uid = self.env.uid
        company_id = self.env.company.id
        self._cr.execute(query, (model_name, uid, company_id, uid))

        return [row[0] for row in self._cr.fetchall()]


    def _compute_domain_keys(self):
        """
        Return the list of context keys to use for caching ``_compute_domain``.
        """
        return ["allowed_company_ids"]

    def _compute_domain_context_values(self):
        for k in self._compute_domain_keys():
            v = self._context.get(k)
            if isinstance(v, list):
                v = tuple(v)
            yield v

    @api.model
    @tools.conditional(
        "xml" not in config["dev_mode"],
        tools.ormcache(
            "self.env.uid",
            "self.env.company.id",
            "self.env.su",
            "model_name",
            "tuple(self._compute_domain_context_values())",
        ),
    )
    def _compute_domain(self, model_name):
        rules = self._get_types(model_name)
        if not rules:
            # None (not Domain.TRUE): empty Domain is falsy and would hide
            # configured types whose domain is [] (match all records).
            return None

        # browse user and rules as SUPERUSER_ID to avoid access errors!
        all_domains = []
        for rule in rules.sudo():
            all_domains.append(Domain(safe_eval(rule.domain) if rule.domain else []))

        return Domain.OR(all_domains)

    @api.model
    def domain_get(self, model_name, get_not=False):
        dom = self._compute_domain(model_name)
        if dom is None:
            return None
        dom = Domain(dom)
        if get_not:
            return ~dom
        return dom

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self.env.registry.clear_cache()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    @api.onchange("apply_for_model")
    def _reset_values(self):
        if self.apply_for_model:
            self.document_opt = "Optional"
            self.contact_opt = "None"
            self.date_opt = "None"
            self.period_opt = "None"
            self.item_opt = "None"
            self.quantity_opt = "None"
            self.amount_opt = "None"
            self.reference_opt = "None"
            self.payment_opt = "None"
            self.location_opt = "None"

    def action_archive(self):
        res = super().action_archive()
        # Untick "Is Config?"
        # Delete views
        for r in self:
            r = r.sudo()
            vals = {
                "is_configured": False,
                "state_field_id": False,
            }
            r.write(vals)
            # search for other type same model
            args = [
                ("model_id", "=", r.model_id),
                ("id", "!=", r.id),
                ("is_configured", "=", True),
            ]
            exist = self.search(args, limit=1)
            if not exist:
                r.unlink_views()
        return res

    def unlink_views(self):
        self.ensure_one()
        views = self.get_primary_views()
        for view in views:
            existed_view = self.get_extended_view(view)
            if existed_view:
                existed_view.unlink()

    @api.model
    def _list_all_models(self):
        lang = self.env.lang or "en_US"
        self._cr.execute(
            """
SELECT model, COALESCE(name->>%s, name->>'en_US') FROM ir_model ORDER BY 2
            """,
            [lang],
        )
        return self._cr.fetchall()

    def open_submitted_request(self):
        self.ensure_one()
        res = {
            "name": self.env._("Submitted Requests"),
            "view_mode": "list,form",
            "res_model": "multi.approval",
            "view_id": False,
            "type": "ir.actions.act_window",
            "domain": [("type_id", "=", self.id), ("state", "=", "Submitted")],
        }
        if not self.apply_for_model:
            res.update(
                {
                    "context": {
                        "default_type_id": self.id,
                    }
                }
            )
        return res

    def _domain(self):
        self.ensure_one()
        dmain = safe_eval(self.domain)
        return dmain

    def create_fields(self, f_names, model_id):
        ResField = self.env["ir.model.fields"]
        for f_name, ttype in f_names.items():
            field_record = ResField._get(self.model_id, f_name)
            if not field_record:
                f_vals = {
                    "name": f_name,
                    "field_description": f_name,
                    "ttype": ttype,
                    "copied": False,
                    "model_id": model_id,
                }
                ResField.create(f_vals)

    def get_compute_val(self, f_name):
        vals = f"""
for rec in self:
  rec['{f_name}'] = rec.env['multi.approval.type'].compute_need_approval(rec)
        """
        return vals

    def get_compute_is_approver_val(self, f_name="x_is_approver"):
        return f"""
for rec in self:
  rec['{f_name}'] = rec.env['multi.approval.type'].compute_is_approver(rec)
        """

    def create_compute_field(self, f_name, model_id, compute_val=None):
        ResField = self.env["ir.model.fields"]
        compute_f = ResField._get(self.model_id, f_name)
        compute_val = compute_val or self.get_compute_val(f_name)
        if not compute_f:
            f_vals = {
                "name": f_name,
                "field_description": f_name,
                "ttype": "boolean",
                "copied": False,
                "store": False,
                "model_id": model_id,
                "compute": compute_val,
            }
            ResField.create(f_vals)
        elif compute_f.state == "manual":
            # Update compute function
            compute_f.write({"compute": compute_val})

    def get_primary_views(self):
        domain = [
            ("model", "=", self.model_id),
            ("type", "=", "form"),
            ("mode", "=", "primary"),
            ("inherit_id", "=", False),
        ]
        return self.env["ir.ui.view"].search(domain)

    def get_extended_view(self, view):
        view_name = self._get_view_xmlid(view)
        exist = self.env.ref(view_name, False)
        if exist:
            return exist
        # Support for old version < 17.0
        args = [("inherit_id", "=", view.id), ("name", "=ilike", "approval_view_%")]
        exist = self.env["ir.ui.view"].search(args, limit=1)
        return exist

    def create_views(self, f_name, f_name1, f_name2):
        views = self.get_primary_views()
        if not views:
            raise UserError(self.env._("This model has no form view !"))
        for view in views:
            existed_view = self.get_extended_view(view)
            if existed_view:
                self._sync_document_approver_buttons(existed_view)
                continue
            self._create_view(view, f_name, f_name1, f_name2)

    def _approver_button_nodes(self):
        """Approve / Refuse buttons for the current approver on the document."""
        btn_approve = E.button(
            {"class": "btn-primary", "approval_btn": "1"},
            name="action_document_approve",
            type="object",
            string="Approve",
            groups="multi_level_approval.group_approval_user",
            invisible="not x_is_approver",
        )
        btn_refuse = E.button(
            {"approval_btn": "1"},
            name="action_document_refuse",
            type="object",
            string="Refuse",
            groups="multi_level_approval.group_approval_user",
            invisible="not x_is_approver",
        )
        f_is_approver = E.field(name="x_is_approver", invisible="1")
        return f_is_approver, btn_approve, btn_refuse

    def _sync_document_approver_buttons(self, view, validate=True):
        """Add Approve/Refuse + x_is_approver to an already configured inherit view.

        :param validate: when False (module install/upgrade), write arch_db
            without running ``_check_xml``. Dependent models like
            ``purchase.order`` may not be in the registry yet during upgrade.
        """
        self.ensure_one()
        if validate:
            model_name = view.model or self.model_id
            if model_name and model_name not in self.env:
                _logger.warning(
                    "Skip document Approve/Refuse sync for %s: model %s is not loaded",
                    self.display_name,
                    model_name,
                )
                return False

        arch = etree.fromstring(view.arch)
        if arch.xpath("//button[@name='action_document_approve']"):
            if not arch.xpath("//field[@name='x_is_approver']"):
                for xpath in arch.xpath("//xpath"):
                    xpath.insert(0, E.field(name="x_is_approver", invisible="1"))
                    break
                self._write_view_arch(view, arch, validate=validate)
            return True

        f_is_approver, btn_approve, btn_refuse = self._approver_button_nodes()
        target = None
        for xpath in arch.xpath("//xpath"):
            if xpath.xpath(".//button[@approval_btn='1']") or xpath.get("expr") == "//form/header":
                target = xpath
                break
        if target is None:
            xml = E.xpath(
                f_is_approver,
                btn_approve,
                btn_refuse,
                expr="//form/header",
                position="inside",
            )
            if arch.tag == "data":
                arch.append(xml)
            else:
                arch = E.data(arch, xml)
        else:
            target.append(f_is_approver)
            target.append(btn_approve)
            target.append(btn_refuse)
        self._write_view_arch(view, arch, validate=validate)
        return True

    def _write_view_arch(self, view, arch, validate=True):
        """Persist updated inherit arch; optionally skip XML validation."""
        arch_xml = etree.tostring(arch, encoding="unicode")
        if validate:
            view.write({"arch": arch_xml})
            return
        # Bypass ir.ui.view.write() → _check_xml during module install/upgrade.
        # arch_db is translated jsonb ({"en_US": "<xml>..."}), not plain text.
        from psycopg2.extras import Json

        self.env.cr.execute(
            "SELECT arch_db FROM ir_ui_view WHERE id = %s",
            (view.id,),
        )
        row = self.env.cr.fetchone()
        current = row[0] if row else None
        if isinstance(current, dict) and current:
            langs = list(current.keys())
        else:
            langs = [(view.env.lang or "en_US").replace("-", "_")]
        new_arch_db = {lang: arch_xml for lang in langs}
        self.env.cr.execute(
            """
            UPDATE ir_ui_view
               SET arch_db = %s,
                   write_date = (now() AT TIME ZONE 'UTC'),
                   write_uid = %s
             WHERE id = %s
            """,
            (Json(new_arch_db), self.env.uid, view.id),
        )
        view.invalidate_recordset(["arch", "arch_db"])
        view.env.registry.clear_cache()

    def _create_view(self, view, f_name, f_name1, f_name2):
        """
        1. Find a base view
        2. Check if it has a header path already?
        3. If not, create new header path
        4. Insert buttons inside the header path
            - Request Approval: if there is no request yet
            - View Approval: if already has some
            - Approve / Refuse: when current user is the active approver
        """
        IrView = self.env["ir.ui.view"]
        view_content = self.env[self.model_id]._get_view(view.id)
        view_arch = view_content[0]
        node = IrView.locate_node(
            view_arch,
            E.xpath(expr="//form/header"),
        )
        wiz_act = self.env.ref(
            "multi_level_approval_configuration.request_approval_action", False
        )
        wiz_view_act = self.env.ref(
            "multi_level_approval_configuration.action_open_request", False
        )
        wiz_rework_act = self.env.ref(
            "multi_level_approval_configuration.rework_approval_action", False
        )
        if not wiz_act or not wiz_view_act or not wiz_rework_act:
            raise UserError(self.env._("Not found the action !"))

        f_node = E.field(name=f_name, invisible="1")
        f1_node = E.field(name=f_name1, invisible="1")
        f2_node = E.field(name=f_name2, invisible="1")
        f_is_approver, btn_approve, btn_refuse = self._approver_button_nodes()
        btn_req_node = E.button(
            {"class": "btn-primary", "approval_btn": "1"},
            name=str(wiz_act.id),
            type="action",
            string="Request Approval",
            groups="multi_level_approval.group_approval_user",
            invisible=f"not {f_name} or {f_name2}",
        )
        btn_vie_node = E.button(
            {"approval_btn": "1"},
            name=str(wiz_view_act.id),
            type="action",
            string="View Approval",
            groups="multi_level_approval.group_approval_user",
            invisible=f"not {f_name2}",
        )
        btn_refuse_node = E.button(
            {"approval_btn": "1"},
            name=str(wiz_rework_act.id),
            type="action",
            string="Rework",
            groups="multi_level_approval.group_approval_user",
            invisible=f"{f_name1} != 'refused'",
        )

        # div is insert right after the header
        div_node1 = E.div(
            "This document need to be approved !",
            {"class": "alert alert-info", "style": "margin-top: 5px;", "role": "alert"},
            invisible=f"not {f_name} or {f_name1}",
        )
        div_node2 = E.div(
            "This document has been approved !",
            {"class": "alert alert-info", "style": "margin-top: 5px;", "role": "alert"},
            invisible=f"not {f_name} or {f_name1} != 'approved'",
        )
        div_node3 = E.div(
            "This document has been refused !",
            {
                "class": "alert alert-danger",
                "style": "margin-top: 5px;",
                "role": "alert",
            },
            invisible=f"not {f_name} or {f_name1} != 'refused'",
        )
        div_node = E.div(div_node1, div_node2, div_node3)

        header_children = (
            f_node,
            f1_node,
            f2_node,
            f_is_approver,
            btn_approve,
            btn_refuse,
            btn_req_node,
            btn_vie_node,
            btn_refuse_node,
        )

        # Create header tag if there is not yet
        if node is None:
            header_node = E.header(*header_children)
            # find a sheet
            sheet_node = IrView.locate_node(
                view_arch,
                E.xpath(expr="//form/sheet"),
            )
            expr = "//form/sheet"
            position = "before"
            if sheet_node is None:
                expr = "//form"
                position = "inside"
            xml = E.xpath(header_node, div_node, expr=expr, position=position)
        else:
            xml0 = E.xpath(
                *header_children,
                expr="//form/header",
                position="inside",
            )
            xml1 = E.xpath(div_node, expr="//form/header", position="after")
            xml = E.data(xml0, xml1)
        xml_content = etree.tostring(xml, pretty_print=True, encoding="unicode")
        new_view_name = self._get_view_name(view)
        new_view = IrView.create(
            {
                "name": new_view_name,
                "model": self.model_id,
                "inherit_id": view.id,
                "arch": xml_content,
            }
        )

        # create new field for model
        self.env["ir.model.data"].create(
            {
                "module": "multi_level_approval_configuration",
                "name": new_view_name,
                "model": "ir.ui.view",
                "noupdate": True,
                "res_id": new_view.id,
            }
        )

    def _get_view_xmlid(self, view):
        view_name = self._get_view_name(view)
        return f"multi_level_approval_configuration.{view_name}"

    def _get_view_name(self, view):
        return f"approval_view_extend_{view.id}"

    def check_state_field(self):
        """
        if no state field is detected, return a window action
        """
        if self.state_field_id:
            return False
        dmain = self._domain()
        if not dmain:
            raise UserError(self.env._("Domain is required !"))
        potential_f = ["state", "state_id", "stage", "stage_id", "status", "status_id"]
        state_field = ""
        dmain_fields = []
        for d in dmain:
            if not d or not isinstance(d, (list | tuple)):
                continue
            dmain_fields += [d[0]]
            if d[0] in potential_f:
                state_field = d[0]
                break
        if state_field:
            ResField = self.env["ir.model.fields"]
            field_record = ResField._get(self.model_id, state_field)
            self.write({"state_field_id": field_record.id})
        else:
            view = self.env.ref(
                "multi_level_approval_configuration.multi_approval_type_view_form_popup"
            )
            ResModel = self.env["ir.model"]
            model_id = ResModel._get_id(self.model_id)
            ctx = {"dmain_fields": dmain_fields, "res_model_id": model_id}
            return {
                "name": self.env._("Select State Field"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "multi.approval.type",
                "views": [(view.id, "form")],
                "view_id": view.id,
                "res_id": self.id,
                "target": "new",
                "context": ctx,
            }

    def clean_created_fields(self, model_id):
        """
        When setup the configuration for account.move, the fields are
        created for account.payment as well. but, their states are not manual
        So, it raises an error.
        Need to remove them in this case.
        """
        field_names = [
            "x_review_result",
            "x_has_request_approval",
            "x_potential_type_id",
            "x_need_approval",
            "x_is_approver",
        ]
        records = (
            self.env["ir.model.fields"]
            .sudo()
            .search(
                [
                    ("name", "in", field_names),
                    ("state", "!=", "manual"),
                    ("model_id", "=", model_id),
                ]
            )
        )
        if records:
            _sql = """
                UPDATE ir_model_fields
                SET state = 'manual',
                    related=NULL
                WHERE id IN %s
            """
            self.env.cr.execute(_sql, (tuple(records.ids),))
            records2 = records.filtered(
                lambda r: r.name != "x_need_approval" and not r.store
            )
            if records2:
                _sql = """
                    UPDATE ir_model_fields
                    SET store = true
                    WHERE id IN %s
                """
                self.env.cr.execute(_sql, (tuple(records2.ids),))
            self.env.flush_all()

    def action_configure(self):
        self.ensure_one()
        self = self.sudo()
        if not self.active:
            return False
        ResModel = self.env["ir.model"]

        # Check state / stage field
        ret_act = self.check_state_field()
        if ret_act:
            return ret_act

        model_id = ResModel._get_id(self.model_id)
        self.clean_created_fields(model_id)

        # Create new fields
        f_name_dict = {
            "x_review_result": "char",
            "x_has_request_approval": "boolean",
            "x_potential_type_id": "integer",
        }
        f_names = ["x_review_result", "x_has_request_approval"]
        self.create_fields(f_name_dict, model_id)

        # Create compute field
        compute_field = "x_need_approval"
        self.create_compute_field(compute_field, model_id)
        self.create_compute_field(
            "x_is_approver",
            model_id,
            compute_val=self.get_compute_is_approver_val(),
        )

        # create extension view
        self.create_views(compute_field, f_names[0], f_names[1])
        self.is_configured = True

    @api.model
    def compute_need_approval(self, rec):
        dmain = self.domain_get(rec._name)
        # NewId is falsy and exists() treats new records as existing in Odoo 19.
        # Skip unsaved records before searching (domains reject NewId).
        if not rec.id or dmain is None or not rec.exists():
            return False
        dmain = Domain("id", "=", rec.id) & Domain(dmain)
        try:
            if rec.sudo().search_count(dmain):
                return True
        except ValueError:
            _logger.error(self.env._("Domain of an Approval type is not set properly!"))
        return False

    @api.model
    def compute_is_approver(self, rec):
        """True when the current user is PIC/proxy of a submitted approval for rec."""
        if not rec.id:
            return False
        approval = rec.env["multi.approval"].search(
            [
                ("origin_ref", "=", f"{rec._name},{rec.id}"),
                ("state", "=", "Submitted"),
            ],
            limit=1,
        )
        return bool(approval and approval.is_pic)

    @api.model
    def update_x_field(self, obj, fi, val=True, raise_if_not_exist=True):
        if hasattr(obj, fi):
            obj.sudo().write({fi: val})
        elif raise_if_not_exist:
            raise UserError(self.env._("Something wrong !"))

    @api.model
    def _get_eval_context(self, request, record=None):
        """evaluation context to pass to safe_eval"""
        if not record:
            raise UserError(self.env._("Something is wrong !"))

        def log(message, level="info"):
            message = str(message)
            with self.pool.cursor() as cr:
                cr.execute(
                    """
INSERT INTO ir_logging(
    create_date, create_uid, type, dbname, name, level, message, path, line, func
)
VALUES (NOW() at time zone 'UTC', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        self.env.uid,
                        "server",
                        self._cr.dbname,
                        __name__,
                        level,
                        message,
                        "approval",
                        record.id,
                        record.name,
                    ),
                )

        model_name = record._name
        model = self.env[model_name]
        ctx = self._context.copy()
        ctx.update({"run_python_code": 1})
        eval_context = {
            "uid": self._uid,
            "user": self.env.user,
            # orm
            "env": self.env,
            "model": model,
            # Exceptions
            "UserError": UserError,
            # record
            "record": record.with_context(**ctx),
            # approval request
            "request": request,
            "refused_reason": request.refused_reason or "",
            # helpers
            "log": log,
        }
        return eval_context

    def run(self, request, record=None, action="approve"):
        """ """
        res = False
        for rec in self:
            if record.x_need_approval:
                res = rec._run(request, record, action)
        return res

    def _run(self, request, record, action):
        self.ensure_one()
        res = False
        func_name = f"get_action_{action}_code"
        if hasattr(self, func_name):
            func = getattr(self, func_name)
            python_code = func(action)
            if not python_code:
                return res
            eval_context = self._get_eval_context(request, record)
            res = self.exec_func(python_code, eval_context)
        return res

    def get_action_submit_code(self, action):
        return self.submit_python_code

    def get_action_approve_code(self, action):
        return self.approve_python_code

    def get_action_refuse_code(self, action):
        return self.refuse_python_code

    @api.model
    def exec_func(self, python_code="", eval_context=None, return_val=False):
        if eval_context is None:
            eval_context = {}
        try:
            # Odoo 19: context is mutated in-place; `nocopy` was removed.
            eval_res = safe_eval(
                python_code.strip(),
                eval_context,
                mode="eval" if return_val else "exec",
                filename="multi.approval.type",
            )
            if return_val:
                return eval_res
        except (UserError, ValidationError) as err:
            raise UserError(err) from err
        except Exception as exc:
            _logger.exception("Approval python action failed")
            raise UserError(
                self.env._(
                    "Approval Type is not configured properly, contact your administrator for help!\n%(error)s",
                    error=exc,
                )
            ) from exc
        return eval_context.get("action")

    @api.model
    @tools.ormcache()
    def _get_applied_models(self):
        args = [("is_configured", "=", True)]
        types = self.search(args)
        model_names = types.mapped("model_id")
        return model_names

    @api.model
    def check_rule(self, records, vals):
        """
        1. Get approval type if possible
        2. check (not x_review_result and x_need_approval)
        3. prevent from editing the fields in domain
        """
        if not self.env.user:
            return True
        if self.env.user._is_admin() or self._context.get("run_python_code"):
            return True
        # Find the approval type
        model_name = records._name
        if model_name in ("multi.approval.type", "ir.module.module"):
            return True
        available_models = self._get_applied_models()
        if model_name not in available_models:
            return True
        approval_types = self._get_types(model_name)
        if not approval_types:
            return True
        approval_type = approval_types[0]
        for rec in records:
            if not rec.id:
                continue
            if rec.x_review_result == "approved":
                # Prevent update fields after approved
                field_names = approval_type.constraint_field_names_approved
                if field_names and set(field_names) & set(vals):
                    raise UserError(
                        self.env._(
                            "This document has been approved. You cannot update the value."  # noqa E501
                        )
                    )
                continue
            if not rec.x_need_approval:
                continue
            # Could not update state field
            constraint_field_names = approval_type.constraint_field_names
            if constraint_field_names and set(constraint_field_names) & set(vals):
                raise UserError(self._make_err_msg(rec.x_review_result == "refused",record = rec))
        return True

    def _make_err_msg(self, refused=False,record=False):
        if record:
            error = self.env._("This document need to be approved by manager ! --> Object name %s and id is %s"%(record._name,record.name))
            if refused:
                error = self.env._("This document has been refused by manager ! --> Object name %s and id is %s"%(record._name,record.name))
        else:
            error = self.env._("This document need to be approved by manager !")
            if refused:
                error = self.env._("This document has been refused by manager !")
        return error

    @api.model
    def filter_type(self, types, model_name, res_id, ignore_potential=False):
        # NewId is falsy; Odoo 19 domains also reject NewId values.
        if not types or not res_id:
            return self
        potential_type = False
        if not ignore_potential:
            potential_type = self._get_type_potential(model_name, res_id)
            if potential_type:
                if potential_type not in types:
                    return self
                types = potential_type
        for t in types:
            args = Domain(t._domain() or []) & Domain("id", "=", res_id)
            if self.env[model_name].search(args, limit=1):
                return t
        # Potential type does not map the domain anymore. Remove it
        # if potential_type:
        #     record = self.env[model_name].browse(res_id)
        #     self.update_x_field(
        #         record, "x_potential_type_id", False,
        #         raise_if_not_exist=False
        #     )

        return self

    @api.model
    def _get_type_potential(self, model_name, res_id):
        """
        @returns boolean(type)
        """
        potential_fn = "x_potential_type_id"
        record = self.env[model_name].browse(res_id)
        # exists() returns new records as existing in Odoo 19.
        if record.id and record.exists() and hasattr(record, potential_fn):
            potential_id = record[potential_fn]
            if potential_id:
                return self.browse(potential_id)
        return False

    def cron_send_request(self):
        args = [
            ("auto_request", "=", True),
            ("apply_for_model", "=", True),
            ("is_configured", "=", True),
        ]
        approval_types = self.search(args)
        for approval_type in approval_types:
            approval_type._send_request_auto()

    def _send_request_auto(self):
        self.ensure_one()
        if not self.env.registry.get(self.model_id):
            return False
        dmain = self.domain_get(self.model_id)
        if dmain is None:
            return False
        dmain = Domain(dmain) & Domain("x_has_request_approval", "=", False)
        try:
            records = self.env[self.model_id].sudo().search(dmain)
        except ValueError:
            records = self.env[self.model_id]
            _logger.error(self.env._("Domain of an Approval type is not set properly!"))
        if not records:
            return False
        for record in records:
            self._send_a_request(record)
        return True

    def _send_a_request(self, record):
        """Auto sending the request"""
        try:
            wizard = (
                self.env["request.approval"]
                .with_context(
                    active_model=record._name,
                    active_id=record.id,
                )
                .new({})
            )
            if not wizard.type_id or not wizard.type_id.auto_request:
                # Case: a record meets domain for more than a type.
                # But, its first type is not auto-request
                return False
            with self.env.cr.savepoint():
                request = wizard.action_request(return_request=True)
                # Add followers
                request._add_followers(record)

        except UserError as e:
            _logger.warning(f"Cannot send the request auto, User Error: {e}")
        except Exception as e:
            _logger.warning(f"Cannot send the request auto, error: {e}")
