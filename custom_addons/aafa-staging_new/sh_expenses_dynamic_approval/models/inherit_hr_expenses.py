from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

_STATES = [
    ("draft", "Draft"),
    ("waiting_for_review", "Waiting For Review"),
    ("submit", "Submit"),
    ("approve", "Approve"),
    ("post", "Post"),
    ("done", "Done"),
    ("cancel", "Cancel"),
]

class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense'

    approval_level_id = fields.Many2one(
        'sh.expenses.approval.config', string="Approval Level", compute="compute_approval_level")
    
    level = fields.Integer(string="Next Approval Level", readonly=True)
    state = fields.Selection(selection=_STATES,string="Status",index=True,
        tracking=True,required=True,copy=False,default="draft",)
   
    # state = fields.Selection(selection_add=[
    # ('waiting_for_review', "Waiting For Review"),], ondelete={'waiting_for_review': 'set default'})
    user_ids = fields.Many2many('res.users', string="Users")
    group_ids = fields.Many2many('res.groups', string="Groups", readonly=True)
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search='_search_is_boolean',store=True)
    approval_info_line = fields.One2many(
        'sh.expenses.approval.info', 'hr_expenses_id', readonly=True)
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)
    # hide_admin_fields = fields.Boolean(default=True, compute="_compute_view_po_fields")
    manager_approval = fields.Boolean(compute="_compute_approval_access")   
    request_approve = fields.Boolean(String="Request Approve")   

    @api.depends('approval_level_id')
    def compute_approval_level(self):
        expenses_approval = self.env['sh.expenses.approval.config'].search(
                    [('company_ids.id', 'in', [self.env.company.id])],limit=1)
        # expenses_approval = self.env['sh.expenses.approval.config'].search()
        if expenses_approval:
            self.update({
                'approval_level_id': expenses_approval[0].id
            })
        else:
            self.approval_level_id = False

    @api.depends('approval_level_id','state')
    def _compute_approval_access(self):
        for rec in self:
            if rec.state == 'waiting_for_review':
                print("======primary_approval====",rec.approval_level_id.primary_approval)
                if rec.approval_level_id.primary_approval == 'line_manager':
                    if self.env.user.id == rec.user_id.id:
                    # if self.env.user.employee_id == rec.assigned_manager_id:
                        rec.manager_approval = True
                    else:
                        rec.manager_approval = False
                else:
                    if self.env.user.employee_id == rec.employee_id:
                        rec.manager_approval = True
                    else:
                        rec.manager_approval = False
            else:
                rec.manager_approval = False

    def compute_is_boolean(self):
        if self.env.user.id in self.user_ids.ids or any(item in self.env.user.groups_id.ids for item in self.group_ids.ids):
            self.is_boolean = True
        else:
            self.is_boolean = False

    def _search_is_boolean(self, operator, value):
        results = []

        if value:
            po_ids = self.env['hr.expense'].search([])
            if po_ids:
                for po in po_ids:
                    if self.env.user.id in po.user_ids.ids or any(
                            item in self.env.user.groups_id.ids for item in po.group_ids.ids):
                        results.append(po.id)
        return [('id', 'in', results)]


    def action_submit(self):
        self.write({'state': 'waiting_for_review'})
        self.sudo().activity_update()

    def button_to_approve(self):
        template_id = self.env.ref(
            "sh_expenses_dynamic_approval.email_template_for_approve_expenses_order")

        if self.approval_level_id.expenses_approval_line:
            self.write({
                'state': 'submit',
                'request_approve':True,
                })
            # self.sudo().activity_update()
            lines = self.approval_level_id.expenses_approval_line

            self.approval_info_line = False
            for line in lines:
                dictt = []
                if line.approve_by == 'group':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': False,
                        'group_ids': [(6, 0, line.group_ids.ids)],
                    }))

                if line.approve_by == 'user':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': [(6, 0, line.user_ids.ids)],
                        'group_ids': False,
                    }))

                self.update({
                    'approval_info_line': dictt
                })

            if lines[0].approve_by == 'group':
                self.write({
                    'level': lines[0].level,
                    'group_ids': [(6, 0, lines[0].group_ids.ids)],
                    'user_ids': False
                })

                users = self.env['res.users'].search(
                    [('groups_id', 'in', lines[0].group_ids.ids)])

                if template_id and users:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if users:
                    for user in users:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for Expenses order %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                    self.env['bus.bus']._sendone(notifications)


            if lines[0].approve_by == 'user':
                self.write({
                    'level': lines[0].level,
                    'user_ids': [(6, 0, lines[0].user_ids.ids)],
                    'group_ids': False
                })

                if template_id and lines[0].user_ids:
                    for user in lines[0].user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if lines[0].user_ids:
                    for user in lines[0].user_ids:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for expenses order %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                    self.env['bus.bus']._sendone(notifications)

        # else:
        #     # self.action_confirm()
        #     super(HrExpenses, self).action_submit()


    def action_approve(self):
        print("AAAAAAAAAAAAAAAAAA----------")
        template_id = self.env.ref(
            "sh_expenses_dynamic_approval.email_template_for_approve_expenses_order")

        info = self.approval_info_line.filtered(
            lambda x: x.level == self.level)

        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        line_id = self.env['sh.expenses.approval.line'].search(
            [('expenses_approval_config_id', '=', self.approval_level_id.id), ('level', '=', self.level)])

        next_line = self.env['sh.expenses.approval.line'].search(
            [('expenses_approval_config_id', '=', self.approval_level_id.id), ('id', '>', line_id.id)], limit=1)

        if next_line:
            if next_line.approve_by == 'group':
                self.write({
                    'level': next_line.level,
                    'group_ids': [(6, 0, next_line.group_ids.ids)],
                    'user_ids': False
                })
                users = self.env['res.users'].search(
                    [('groups_id', 'in', next_line.group_ids.ids)])

                # if template_id and users and self.approval_level_id.is_boolean:
                #     for user in users:
                #         template_id.sudo().send_mail(self.id, force_send=True, email_values={
                #             'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.user_id.email})

                if template_id and users and not self.approval_level_id.is_boolean:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if users:
                    for user in users:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for expenses order %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                        
                    self.env['bus.bus']._sendone(notifications)

            if next_line.approve_by == 'user':
                self.write({
                    'level': next_line.level,
                    'user_ids': [(6, 0, next_line.user_ids.ids)],
                    'group_ids': False
                })
                # if template_id and next_line.user_ids and self.approval_level_id.is_boolean:
                #     for user in next_line.user_ids:
                #         template_id.sudo().send_mail(self.id, force_send=True, email_values={
                #             'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.user_id.email})

                if template_id and next_line.user_ids and not self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if next_line.user_ids:
                    for user in next_line.user_ids:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for expenses order %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                    self.env['bus.bus']._sendone(notifications)

        else:
            template_id = self.env.ref(
                "sh_expenses_dynamic_approval.email_template_for_confirm_expenses_order")
            if template_id:
                template_id.sudo().send_mail(self.id, force_send=True, email_values={
                    'email_from': self.env.user.email, 'email_to': self.user_id.email})

            notifications = []
            if self.user_id:
                notifications.append([self.user_id.partner_id, 'res.partner', {
                    'title': _('Notitification'),
                    'message': 'You have approval notification for expenses order %s' % (self.name),
                    'sticky': True,
                    'warning': True
                }])
                self.env['bus.bus']._sendone(notifications)

            self.write({
                'level': False,
                'group_ids': False,
                'user_ids': False,
                'state': 'approve',
            })
            super(HrExpenseSheet, self).action_approve()

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
