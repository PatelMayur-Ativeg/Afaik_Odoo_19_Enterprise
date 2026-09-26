from odoo import models, fields, api, exceptions, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import logging


_logger = logging.getLogger(__name__)


class PRReportXlsx(models.TransientModel):
    _name = 'pr.report.popup'
    _description = 'PR Report Xlsx'

    from_date = fields.Date("From Date", default=fields.Date.today())
    to_date = fields.Date("To Date", default=fields.Date.today())
    state = fields.Selection([("draft", "Draft"),
    ("waiting_for_approval", "Waiting for Approval"),
    ('in_progress', 'In Progress'),
    ("reject", "Rejected"),
    ("done", "Done")])
    over_budget = fields.Boolean('Over Budget', default=False)
    within_budget = fields.Boolean('Within Budget', default=False)
    product_id = fields.Many2one('product.product')
    employee_id = fields.Many2one('hr.employee')
    department_id = fields.Many2one('hr.department')
    pr_category_id = fields.Many2one("purchase.request.category", string="Category")
    request_action = fields.Selection([('internal_transfer', 'Internal Picking'),('purchase_order', 'Purchase Order'),('partial', 'Partial')], string="Request Action",copy=False)
    vendor_id = fields.Many2one('res.partner')



    @api.constrains('from_date', 'to_date')
    def _check_date(self):
        if self.from_date > self.to_date:
            raise ValidationError("From Date must before To Date ")

    def generate_pr_report(self):
        _logger.info(self)
        filter  = ''
        if self.from_date and self.to_date:
            filter += " pr.date_start >='"+str(self.from_date)+"' and pr.date_start <='"+str(self.to_date)+"'"
        if self.employee_id:
            filter += " and pr.employee_id ="+str(self.employee_id.id)
        if self.department_id:
            filter += " and pr.department_id ="+str(self.department_id.id)
        if self.state:
            filter += " and pr.state ='"+str(self.state)+"'"
        if self.over_budget:
            filter += " and pr.check_budget_amt = True"
        if self.within_budget:
            filter += " and pr.check_budget_amt = False"
        if self.pr_category_id:
             filter += " and pr.pr_category_id ="+str(self.pr_category_id.id)
        if self.product_id:
            filter += " and prl.product_id ="+str(self.product_id.id)
        if self.request_action:
            filter += " and prl.requisition_action = '"+str(self.request_action)+"'"
        if self.vendor_id:
            filter += " and prl.vendor_id ="+str(self.vendor_id.id)
        
        _logger.info(filter)
        self._cr.execute(
            """
            select pr.name as ref,pr.date_start as date,he.name as employee,hd.name as department,prc.name as pr_category,aa.name as analytic,prl.requisition_action as paction,
                prl.name as product,prl.product_qty as request_qty,prl.qty_to_buy as qty_to_buy,prl.pending_qty_to_receive as qty_to_receive,rp.display_name as vendor
            from purchase_request pr
            left join purchase_request_line prl on prl.request_id = pr.id
            left join hr_employee he on pr.employee_id=he.id
            left join hr_department hd on pr.department_id=hd.id
            left join account_analytic_account aa on pr.analytic_account_id = aa.id
            left join product_product pp on prl.product_id = pp.id
            left join product_template pt on pp.product_tmpl_id = pt.id
            left join res_partner rp on prl.vendor_id = rp.id
            left join purchase_request_category prc on pr.pr_category_id = prc.id
            where   """ +str(filter)+ """order by pr.date_start"""
        
        )
        results = self._cr.dictfetchall()
        data = {}
        finl_list = []
        if results:
            i = 0
            datas={}
            lists =[]
            final_data = {}
            for line in results:
                category = line['pr_category'] or ''
                if line['paction']:
                    if line['paction'] == 'purchase_order':
                        action = "Purchase Order"
                    elif line['paction'] == 'partial':
                        action = "Partial"
                    elif line['paction'] == 'internal_transfer':
                        action = "Internal Picking"
                else:
                    action = ''
                    
                datas = {
                    "ref": line['ref'],
                    "date_start": line["date"],
                    "employee":line['employee'],
                    "department": line['department'],
                    "category": category ,
                    "analytic": line["analytic"],
                    "action": action,
                    "product": line["product"],
                    "request_qty": line["request_qty"],
                    "qty_to_buy": line["qty_to_buy"],
                    "qty_to_receive": line['qty_to_receive'],
                    "vendor": line['vendor']
                }
                lists.append(datas)
            final_data['datas']= lists
            finl_list.append(final_data)
            data = {'form_data': finl_list}
        data = {'form_data': finl_list}
        return self.env.ref('pr_report_xlsx.pr_report_xlsx').report_action(self, data=data)
