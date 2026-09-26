from odoo import models, fields, api, _
import base64
import io
import xlrd
from openpyxl import load_workbook, Workbook
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class AafaqImportAttachment(models.Model):
    _name = "aafaq.map.attachment"
    _description = "Aafaq Map Attachment"
    _order = "id desc"

    internal_id = fields.Char(string="Internal ID", help="Reference ID from Internal system Aafaq", index=True, copy=False) 
    attachment_id = fields.Many2one('ir.attachment',string="Attachment")
    company_id = fields.Many2one("res.company", string="Company", required=True)
    aafaq_queue_id = fields.Many2one('aafaq.import.queue', ondelete='set null', string='Import Queue')