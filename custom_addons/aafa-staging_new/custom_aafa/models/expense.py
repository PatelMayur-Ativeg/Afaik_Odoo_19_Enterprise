from odoo import models, fields, api, _
from datetime import datetime, time, date, timedelta

class HrExpense(models.Model):
    _inherit = 'hr.expense'


    @api.depends('product_id', 'account_id')
    def _compute_analytic_distribution(self):
        
        for expense in self:
            expense.analytic_distribution = False


# class HrExpenseSheet(models.Model):
#     _inherit = 'hr.expense.sheet'

    budget_id = fields.Many2one('budget.analytic', string="Budget")
    budget_planned_amt = fields.Monetary(compute='compute_planned_amt')
    practical_amt = fields.Monetary(compute='_compute_practical_amount')
    forecast_amt = fields.Monetary(compute='_compute_forecast_amt', string="PR Amount")
    forecast_remaining_amt = fields.Monetary(compute='_compute_forecast_amt', string="Remaining Budget")
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic Account",
        copy=False,  # Unrequired company
       )


    @api.depends('budget_id', 'analytic_account_id','product_id','total_amount')
    def _compute_forecast_amt(self):
        for line in self:
            subtotal = 0
            date_to = line.budget_id.date_to
            date_from = line.budget_id.date_from
            if line.analytic_account_id.id:
                analytic_line_obj = self.env['account.analytic.line']
                domain = [('account_id', '=', line.analytic_account_id.id),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ]

                where_query = analytic_line_obj._where_calc(domain)
                analytic_line_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT SUM(amount) from " + from_clause + " where " + where_clause
                self.env.cr.execute(select, where_clause_params)
                practical_amt = self.env.cr.fetchone()[0] or 0.0
                for rec in line:
                    subtotal += rec.total_amount
                # for rec in line.new_line_ids:
                #     subtotal += rec.cost_price*rec.request_qty
                line.forecast_amt = subtotal
                line.forecast_remaining_amt = (line.budget_planned_amt - (line.practical_amt+line.forecast_amt))
            else:
                line.forecast_amt = 0.0
                line.forecast_remaining_amt = (line.budget_planned_amt - (line.practical_amt+line.forecast_amt))

    @api.depends('budget_id', 'analytic_account_id')
    def _compute_practical_amount(self):
        for line in self:
            date_to = line.budget_id.date_to
            date_from = line.budget_id.date_from
            if line.analytic_account_id.id:
                analytic_line_obj = self.env['account.analytic.line']
                domain = [('account_id', '=', line.analytic_account_id.id),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ]

                where_query = analytic_line_obj._where_calc(domain)
                analytic_line_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT SUM(amount) from " + from_clause + " where " + where_clause
                self.env.cr.execute(select, where_clause_params)
                practical_amt = self.env.cr.fetchone()[0] or 0.0
                line.practical_amt = -1 *practical_amt
            else:
                line.practical_amt = 0.0

    @api.depends('budget_id', 'analytic_account_id')
    def compute_planned_amt(self):
        if self.budget_id and self.analytic_account_id:
            for rec in self.budget_id:
                planned_amt = sum(rec.budget_line_ids.filtered(lambda r: r.analytic_account_id == self.analytic_account_id).mapped('budget_amount'))
                self.budget_planned_amt = -1*planned_amt
        else:
            self.budget_planned_amt = 0


    def action_submit(self):
        if self.employee_id:
            department = self.employee_id.department_id
            if department:
                analytic_account = department.analytic_account_id
                self.analytic_account_id = analytic_account.id if analytic_account else False
                if analytic_account:
                    budget_lines =self.env['budget.line'].search([('analytic_account_id','=',analytic_account.id), ('date_from', '<=', str(self.accounting_date)),('date_to', '>=', str(self.accounting_date))],limit=1)
                    for line in self:
                        line.write({
                            'analytic_distribution': {
                    str(analytic_account.id):100
                    }
                        })
                if budget_lines:
                    self.budget_id = budget_lines.crossovered_budget_id.id
        res = super(HrExpenseSheet, self).action_submit()