# -*- coding: utf-8 -*-
# See LICENSE file for full copyright & licensing details.

from odoo import models
import logging
import base64
import io
# import xlsxwriter


_logger = logging.getLogger(__name__)


class PRReportXlsx(models.AbstractModel):
    _name = 'report.pr_report_xlsx.pr_report_xlsx'
    _description = 'PR Report XLSX'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, adjs):
        _logger.info(data['form_data'])
        values = data['form_data']
        table_head = workbook.add_format(
            {'align': 'left', 'bold': True, 'border': 1})
        sheet_head = workbook.add_format(
            {'align': 'left', 'bold': True,})

        sheet = workbook.add_worksheet('Purchase Request Report')
        sheet.set_column(0, 0, 25)
        sheet.set_column(1, 16, 25)

        date_style = workbook.add_format({
            'text_wrap': True, 
            'num_format': 'dd-mm-yyyy',
            'align': 'left',})
        merge_format = workbook.add_format({
            'bold': 1,
            'font':16,
            'align': 'center',
            'valign': 'vcenter',})
        merge_format.set_font_name('Times New Roman')
        merge_format.set_font_size(18)
        merge_format.set_italic()
        sheet_head.set_italic()
        # sheet_head.set_align('center')
        # sheet_head.set_text_wrap()

        sheet.merge_range('C3:D3', 'PURCHASE REQUEST REPORT', merge_format)
        sheet.write(6, 0, 'From Date : ', sheet_head)
        sheet.write(7, 0, 'To Date :', sheet_head)
        sheet.write(6, 1, adjs.from_date, date_style)
        sheet.write(7, 1, adjs.to_date, date_style)

        # //=================Company Header=======================
        image_width = 60.0
        image_height = 100.0

        cell_width = 40.0
        cell_height = 50.0

        x_scale = cell_width/image_width
        y_scale = cell_height/image_height
    
        company=self.env.company
        company_name=company.name
        company_address=f"{company.street}{company.street2}"
        company_country=company.country_id.name
        if company.logo:
            image_data=io.BytesIO(base64.b64decode(company.logo))
        else:
            image_data=False
        # sheet.insert_image('F1:G1','logo.png',{'image_data':image_data})
        sheet.insert_image('F1', 'logo.png',
                               {'image_data':image_data,'x_scale': x_scale, 'y_scale': y_scale})
        # sheet.write(2,1,company_name,sheet_head)
        sheet.merge_range('E7:G7',company_address,sheet_head)
        sheet.merge_range('F8:G8',company_country,sheet_head)
        # sheet.merge_range('F3:G3', adjs.employee_id.company_id.street, sheet_head)
        # //========================================
        row=9
        sheet.write(row, 0, 'Reference', table_head)
        sheet.write(row, 1, 'Date', table_head)
        sheet.write(row, 2, 'Employee', table_head)
        sheet.write(row, 3, 'Department', table_head)
        sheet.write(row, 4, 'Category', table_head)
        sheet.write(row, 5, 'Analytic Account', table_head)
        sheet.write(row, 6, 'Request Action', table_head)
        sheet.write(row, 7, 'Product', table_head)
        sheet.write(row, 8, 'Request Qty', table_head)
        sheet.write(row, 9, 'Qty to Buy', table_head)
        sheet.write(row, 10, 'Qty to Receive', table_head)
        sheet.write(row, 11, 'Vendor', table_head)
        count =row
        for obj in values:
            for line in obj['datas']:
                count = count + 1
                sheet.write(count, 0, line['ref'], '')
                sheet.write(count, 1, line['date_start'], '')
                sheet.write(count, 2, line['employee'], '')
                sheet.write(count, 3, line['department'], '')
                sheet.write(count, 4, line['category'], '')
                sheet.write(count, 5, line['analytic'], '')
                sheet.write(count, 6, line['action'], '')
                sheet.write(count, 7, line['product'], '')
                sheet.write(count, 8, line['request_qty'], '')
                sheet.write(count, 9, line['qty_to_buy'], '')
                sheet.write(count, 10, line['qty_to_receive'], '')
                sheet.write(count, 11, line['vendor'], '')