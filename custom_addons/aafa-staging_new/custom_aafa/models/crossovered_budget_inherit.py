from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class CrossoveredBudget(models.Model):
    _inherit = "budget.analytic"

    state = fields.Selection(selection_add=[
        ('cfo_approve', 'CFO Approve'),
        ('coo_approve', 'COO Approve'),
        # ('ceo_approve', 'CEO Approve'),
        ('done', 'CEO / Done'),],
        ondelete={'cfo_approve': 'set default', 'coo_approve': 'set default', })
    budget_approval_info_line = fields.One2many(
        'budget.approval.info', 'cross_budget_id',readonly=1)
    approval_level_id = fields.Many2one(
        'budget.approval.config', string="Approval Level",)
        # 'budget.approval.config', string="Approval Level", compute="compute_approval_level")
    level = fields.Integer(string="Next Approval Level", readonly=True)
    user_ids = fields.Many2many('res.users', string="Users")
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search='_search_is_boolean')
    # is_boolean = fields.Boolean(string="Valid user Boolean",search='_search_is_boolean',default=True)
    
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)
    # hide_admin_fields = fields.Boolean(default=True, compute="_compute_view_po_fields")
    sum_planned_amount = fields.Float(string="Sum Practical Amount", readonly=True, compute='_compute_sum_planned_amt')
    label_name = fields.Char(string="Next Approval Level Name",)
    # label_type = fields.Selection([('cfo_approve', 'CFO Approve'),('coo_approve','COO Approve'),('ceo_approve','CEO Approve')])
    is_sent_email = fields.Boolean(string="Send Email",)

    def _compute_sum_planned_amt(self):
        for rec in self:
            total = 0.0
            if rec.budget_line_ids:
                for line in rec.budget_line_ids:
                    total += line.budget_amount
            rec.sum_planned_amount = total

    # //=========Visible button to users=====
    def compute_is_boolean(self):
        print("BBBBBBBBBBBBBBBBB")
        print("self.env.user.id----",self.env.user)
        if self.is_sent_email:
            if self.env.user.id in self.user_ids.ids:
                self.is_boolean = True
            else:
                self.is_boolean = False
        else:
            self.is_boolean = True

    def _search_is_boolean(self, operator, value):
        results = []
        if value:
            cb_ids = self.env['budget.analytic'].search([])
            if cb_ids:
                for cb in cb_ids:
                    if self.env.user.id in cb.user_ids.ids:
                        results.append(po.id)
        return [('id', 'in', results)]


    def action_budget_confirm(self):
        template_id = self.env.ref("custom_aafa.email_template_for_approve_budget")
        if self.budget_line_ids:

            # //======fetching all each config lines==========
            lines = self.env['budget.approval.line'].search([])
            for line in lines:
                dictt = []
                dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': [(6, 0, line.user_ids.ids)],
                        'label_type':line.label_type,
                    }))
                self.update({
                    'budget_approval_info_line': dictt,
                })

            # //=========checking user existance for button access========== 
            line_id = self.env['budget.approval.line'].search([('level', '=', self.level)])
            # if self.env.user.id in line_id.user_ids.ids:
            #     self.is_boolean = True
            # else:
            #     self.is_boolean = False
            self.update({
                    'user_ids': [(6, 0, line_id.user_ids.ids)],
                    'level': line_id.level,
                    'state': 'done',
                    'label_name':line_id.label_type,
                    'is_sent_email':line_id.is_send_email,
                })

            print("=line-id=send===CFO====",line_id.is_send_email)
            if line_id.is_send_email:
                # if self.env.user.id in line_id.user_ids.ids:
                #     self.is_boolean = True
                # else:
                #     self.is_boolean = False
                # //==========sending Email Template==========
                if template_id and lines[0].user_ids:
                    odoobot = self.env.ref('base.user_root').email
                    # 'email_from': self.env.user.email
                    for user in lines[0].user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': odoobot, 'email_to': user.email})
                
                # //==========sending Notification Template==========        
                notifications = []
                if lines[0].user_ids:
                    for user in lines[0].user_ids:
                        notifications.append([user.partner_id, 'res.partner', {
                                'title': _('Notitification'),
                                'message': 'You have approval notification for Purchase order %s' % (self.name),
                                'sticky': True,
                                'warning': True
                            }])
                        self.env['bus.bus']._sendone(notifications)

                    # self.write({'state': 'confirm'})
            else:
                self.update({'is_boolean':True,})

        else:
            raise ValidationError('Enter Budget Lines')    

    def action_cfo_approve(self):
        template_id = self.env.ref("custom_aafa.email_template_for_approve_budget")

        # ===== Approval Info =====
        info = self.budget_approval_info_line.filtered(lambda x: x.level == self.level)
        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        # ===== Current Line =====
        line_id = self.env['budget.approval.line'].search(
            [('level', '=', self.level)],
            limit=1
        )

        # ===== Next Line (IMPORTANT FIX) =====
        next_line = self.env['budget.approval.line'].search(
            [('level', '>', self.level)],
            order='level asc',
            limit=1
        )

        if next_line:
            self.update({
                'user_ids': [(6, 0, next_line.user_ids.ids)],
                'level': next_line.level,
                'label_name': next_line.label_type,
                'state': 'cfo_approve',
                'is_sent_email': next_line.is_send_email,
            })

            print("=line-id=send==CFO=====", next_line.is_send_email)

            if next_line.is_send_email:
                for user in next_line.user_ids:
                    odoobot = self.env.ref('base.user_root').email
                    template_id.sudo().send_mail(
                        self.id,
                        force_send=True,
                        email_values={
                            'email_from': odoobot,
                            'email_to': user.email
                        }
                    )

                # Notification
                for user in next_line.user_ids:
                    self.env['bus.bus']._sendone(
                        user.partner_id,
                        'res.partner',
                        {
                            'title': _('Notification'),
                            'message': f'You have approval notification for Purchase order {self.name}',
                            'sticky': True,
                            'warning': True
                        }
                    )
            else:
                self.update({'is_boolean': True})

    def action_coo_approve(self):
        template_id = self.env.ref("custom_aafa.email_template_for_approve_budget")

        # ===== Approval Info =====
        info = self.budget_approval_info_line.filtered(lambda x: x.level == self.level)
        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        # ===== Next Line (FIXED) =====
        next_line = self.env['budget.approval.line'].search(
            [('level', '>', self.level)],
            order='level asc',
            limit=1
        )

        if not next_line:
            self.update({'is_boolean': True})
            return

        # ===== Update =====
        self.update({
            'user_ids': [(6, 0, next_line.user_ids.ids)],
            'level': next_line.level,
            'label_name': next_line.label_type,
            'state': 'coo_approve',
            'is_sent_email': next_line.is_send_email,
        })

        print("=line-id=send====COO===", next_line.is_send_email)

        if next_line.is_send_email:

            # ===== Email =====
            for user in next_line.user_ids:
                odoobot = self.env.ref('base.user_root').email
                template_id.sudo().send_mail(
                    self.id,
                    force_send=True,
                    email_values={
                        'email_from': odoobot,
                        'email_to': user.email
                    }
                )

            # ===== Notification =====
            for user in next_line.user_ids:
                self.env['bus.bus']._sendone(
                    user.partner_id,
                    'res.partner',
                    {
                        'title': _('Notification'),
                        'message': f'You have approval notification for Purchase order {self.name}',
                        'sticky': True,
                        'warning': True
                    }
                )
        else:
            self.update({'is_boolean': True})

    def action_ceo_approve(self):
        # //========action after approval=    
        info = self.budget_approval_info_line.filtered(
            lambda x: x.level == self.level)
        picking_only = False
        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user
        self.write({'state': 'done'})

    def action_budget_cancel(self):
        self.update({
            'user_ids': [(5,0,0)],
            'level': 0,
            'budget_approval_info_line': [(5,0,0)],
            'state': 'cancel',
            'label_name':False,
            # 'is_boolean': True,
            # 'is_sent_email':True,

        })

    def action_budget_draft(self):
        self.write({'state': 'draft'})
        # self.update({
        #     'user_ids': [(5,0,0)],
        #     'level': 0,
        #     'budget_approval_info_line': [(5,0,0)],
        #     'state': 'draft',
        #     'label_name':False,
        #     'is_boolean': False,
        #     # 'is_sent_email':True,

        # })

class CrossoveredBudgetLines(models.Model):
    _inherit = "budget.line"

    real_amount = fields.Monetary(compute='_compute_real_amount', string='Real Amount', help="Total earned/spent. Amount")
    
    @api.depends('budget_amount')
    def _compute_real_amount(self):
        for line in self:
            real_amt = 0.00
            real_amt=line.budget_amount-line.achieved_percentage
            line.real_amount=real_amt
 