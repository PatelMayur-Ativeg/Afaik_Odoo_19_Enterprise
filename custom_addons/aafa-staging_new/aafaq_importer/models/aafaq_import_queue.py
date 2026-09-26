from odoo import models, fields, api, _
from markupsafe import Markup
import base64
import csv
import io
import os
import zipfile
import xlrd
from openpyxl import load_workbook, Workbook
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
from collections import defaultdict
import logging
import requests
import re

from .aafaq_import_constants import (
    COA_ACCOUNT_TYPE_MAP,
    IMPORT_FILE_EXTENSIONS,
    IMPORT_FILE_PRIORITY,
    RECORD_TYPE_JOURNAL_MAP,
    RECORD_TYPE_SELECTION,
    RECORD_TYPE_SEQUENCE_MAP,
)

_logger = logging.getLogger(__name__)

MIME_MAP = {
    "application/pdf": ".pdf",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "text/csv": ".csv",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

REQUIRED_HEADERS = {
    'journal_entries': [
            "TRAN_CURRENCY", "ACCT_NAME", "ACCT_NAME", "ENTRY_USER_ID", "ENTRY_DATE", 
            "DR_CR_IND", "TRAN_AMT", "TRAN_RMKS", "TRAN_PARTICULAR", "RPT_CODE","GL_SUB_HEAD_DESC"
            ],
    'adj_entries': ["VALUE_DATE", "TRAN_DATE", "ACCT_NUM", "DR_CR_IND", "TRAN_AMT", "TRAN_CURRENCY", "TRAN_PARTICULAR", "TRAN_RMKS", "FREE_TEXT"],
    'coa': ["Currency", "Code", "Account Name", "Odoo Type", "FS Grouping"],
}

RECORD_KEY_MAP = {
    'journal_entries': ["VALUE_DATE", "TRAN_ID"],
    # False: do not split the file; all rows become one journal entry.
    'adj_entries': 'VALUE_DATE',
    'coa': 'Code',
}

COMPANY_TYPE_MAP = {
    'Individual': 'person',
    'Company': 'company',
    'person': 'person',
    'company': 'company'
}

def date_to_excel_serial(date_str, date_format="%d-%m-%Y %H:%M:%S"):
    """
    Convert date string to Excel serial number (1900 date system)
    If format doesn't match, return original value
    """
    try:
        # Try parsing with given format
        dt = datetime.strptime(date_str, date_format)

        excel_base_date = datetime(1899, 12, 30)
        delta = dt - excel_base_date

        return delta.days

    except (ValueError, TypeError):
        # If parsing fails → return original value
        return date_str

def normalize_col_val(col_name, val_str):
    """
    Normalize column value:
    - If column name contains 'date' → convert to 'YYYY-MM-DD' (no time)
    - Else return value as-is
    """
    if not val_str:
        return val_str

    if 'date' in (col_name or '').lower():
        val_str = val_str.strip()

        # Case 2: parse other formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except:
                continue

    return val_str

class NetsuiteImportQueue(models.Model):
    _name = "aafaq.import.queue"
    _description = "AAfaq Import Queue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(required=True, tracking=True)
    record_type = fields.Selection(RECORD_TYPE_SELECTION, required=True, tracking=True)
    journal_id = fields.Many2one("account.journal", string="Journal")
    file = fields.Binary("File", required=False)
    filename = fields.Char("Filename")
    state = fields.Selection([
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("failed", "Failed"),
    ], default="draft", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True)
    user_id = fields.Many2one("res.users", string="Salesperson", required=False)
    log = fields.Text("Log / Error Message")
    log_ids = fields.One2many("aafaq.import.log", "queue_id", string="Logs")
    log_count = fields.Integer(string="Log Count", compute="_compute_log_count", store=True)
    move_ids = fields.One2many('account.move', 'affaq_queue_id', string='Move')
    move_count = fields.Integer(string='Move Count', compute='_compute_move_count', store=True)
    entry_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Posted"),
        ],
        string="Journal Entry Status",
        compute="_compute_entry_status",
        store=False,
        help="Done when all linked journal entries are posted; "
             "Draft if any linked entry is still unposted.",
    )
    existing_move_ids = fields.Many2many(
        "account.move",
        "aafaq_import_queue_existing_move_rel",
        "queue_id",
        "move_id",
        string="Already Existing Moves",
    )
    existing_move_count = fields.Integer(
        string="Existing Move Count",
        compute="_compute_existing_move_count",
        store=True,
    )
    updated_partner_ids = fields.Many2many(
        "res.partner",
        "aafaq_import_queue_updated_partner_rel",
        "queue_id",
        "partner_id",
        string="Updated Existing Partners",
    )
    updated_partner_count = fields.Integer(
        string="Updated Partner Count",
        compute="_compute_updated_partner_count",
        store=True,
    )
    customer_ids = fields.One2many('res.partner', 'aafaq_queue_id', string='Customer')
    customer_count = fields.Integer(string='Customer Count', compute='_compute_cus_count', store=True)
    account_ids = fields.One2many('account.account', 'aafaq_queue_id', string='Accounts')
    account_count = fields.Integer(string='Account Count', compute='_compute_account_count', store=True)
    updated_account_ids = fields.Many2many(
        "account.account",
        "aafaq_import_queue_updated_account_rel",
        "queue_id",
        "account_id",
        string="Updated Existing Accounts",
    )
    updated_account_count = fields.Integer(
        string="Updated Account Count",
        compute="_compute_updated_account_count",
        store=True,
    )
    script_att = fields.Binary("Script File")
    import_source = fields.Selection(
        [
            ("manual", "Internal Upload"),
            ("email", "Incoming Email"),
        ],
        string="Source",
        default="manual",
        required=True,
        tracking=True,
        copy=False,
        help="How this import queue was created. Use a dedicated selection, not UTM Source "
             "(that is for marketing campaigns).",
    )
    alias_config_id = fields.Many2one(
        "aafaq.import.alias",
        string="Email Alias",
        ondelete="set null",
        copy=False,
        index=True,
    )
    alias_email = fields.Char(related="alias_config_id.alias_email", string="Alias Email")
    email_from = fields.Char(string="Email From", copy=False)

    @api.depends('customer_ids')
    def _compute_cus_count(self):
        for record in self:
            record.customer_count = len(record.customer_ids)

    @api.depends('account_ids')
    def _compute_account_count(self):
        for record in self:
            record.account_count = len(record.account_ids)

    @api.depends("log_ids")
    def _compute_log_count(self):
        for record in self:
            record.log_count = len(record.log_ids)

    @api.depends("existing_move_ids")
    def _compute_existing_move_count(self):
        for record in self:
            record.existing_move_count = len(record.existing_move_ids)

    @api.depends("updated_partner_ids")
    def _compute_updated_partner_count(self):
        for record in self:
            record.updated_partner_count = len(record.updated_partner_ids)

    @api.depends("updated_account_ids")
    def _compute_updated_account_count(self):
        for record in self:
            record.updated_account_count = len(record.updated_account_ids)

    @api.model
    def _next_queue_name(self, record_type):
        seq_code = RECORD_TYPE_SEQUENCE_MAP.get(record_type)
        return self.env["ir.sequence"].next_by_code(seq_code) if seq_code else _("Import")

    @api.model
    def _mail_get_primary_email_field(self):
        return "email_from"

    def _fill_journal_from_record_type(self, vals):
        record_type = vals.get("record_type")
        if record_type not in RECORD_TYPE_JOURNAL_MAP or vals.get("journal_id"):
            return vals
        journal_name = RECORD_TYPE_JOURNAL_MAP[record_type]
        domain = [("name", "=", journal_name)]
        company_id = vals.get("company_id") or self.env.company.id
        if company_id:
            domain.append(("company_id", "=", company_id))
        journal = self.env["account.journal"].search(domain, limit=1)
        if journal:
            vals["journal_id"] = journal.id
        return vals

    @api.model
    def _extract_import_attachments(self, attachments):
        """Return every Excel/CSV attachment from an incoming email.

        Each item is ``(filename, base64 content)``. Non-spreadsheet files are skipped.
        """
        files = []
        for attachment in attachments or []:
            filename = attachment[0] or "attachment"
            content = attachment[1]
            ext = os.path.splitext(filename)[1].lower()
            if not IMPORT_FILE_PRIORITY.get(ext):
                continue
            if isinstance(content, str):
                content = content.encode("utf-8")
            files.append((filename, base64.b64encode(content)))
        return files

    @api.model
    def _extract_import_attachment(self, attachments):
        """Return the first Excel/CSV attachment, or ``(False, False)``."""
        files = self._extract_import_attachments(attachments)
        return files[0] if files else (False, False)

    def _finalize_email_queue(self):
        """Log the incoming email and process this queue. Failures stay on the queue."""
        self.ensure_one()
        alias_email = self.alias_email or (self.alias_config_id.alias_name or _("n/a"))
        self._message_log(body=Markup("<p>%s</p>") % _(
            "Import queue created from incoming email to %(alias)s (from %(email_from)s).",
            alias=alias_email,
            email_from=self.email_from or _("unknown sender"),
        ))
        try:
            if not self.file:
                raise ValidationError(_(
                    "No Excel or CSV attachment found. Attach a .xlsx, .xls or .csv file."
                ))
            self.action_process_queue()
        except Exception as exc:
            self._log_email_failure(str(exc), exception=exc)

    def _log_email_failure(self, message, exception=None):
        self.ensure_one()
        error = exception or UserError(message)
        level, error_type = self._classify_exception(error)
        alias_email = self.alias_email or (self.alias_config_id.alias_name or _("Unknown alias"))
        full_message = str(message)
        self.write({
            "state": "failed",
            "log": (self.log or "") + ("\n" if self.log else "") + _(
                "Email alias %(alias)s: %(error)s",
                alias=alias_email,
                error=full_message,
            ),
        })
        self._create_log(
            message=full_message,
            level=level,
            error_type=error_type,
            model=self._name,
            data={
                "alias": alias_email,
                "email_from": self.email_from,
                "filename": self.filename,
            },
        )
        self._message_log(body=Markup("<p>%s</p>") % _(
            "Email alias %(alias)s: %(error)s",
            alias=alias_email,
            error=full_message,
        ))

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        custom_values.setdefault("import_source", "email")
        if msg_dict.get("email_from") and not custom_values.get("email_from"):
            custom_values["email_from"] = msg_dict["email_from"]
        if not custom_values.get("name"):
            custom_values["name"] = self._next_queue_name(custom_values.get("record_type"))
        if not custom_values.get("company_id"):
            custom_values["company_id"] = self.env.company.id
        self._fill_journal_from_record_type(custom_values)

        files = self._extract_import_attachments(msg_dict.get("attachments"))
        # No spreadsheet: still create one queue so the failure is visible.
        if not files:
            files = [(False, False)]

        first = self.env["aafaq.import.queue"]
        for index, (filename, file_b64) in enumerate(files):
            vals = dict(custom_values)
            if index:
                vals["name"] = self._next_queue_name(vals.get("record_type"))
            if filename:
                vals["filename"] = filename
                vals["file"] = file_b64
            if index == 0:
                record = super().message_new(msg_dict, custom_values=vals)
                first = record
            else:
                record = self.create(vals)
            record._finalize_email_queue()
        return first

    def action_view_customer(self):
        self.ensure_one()
        action = self.env.ref('contacts.action_contacts').read()[0]
        action['domain'] = [('id', 'in', self.customer_ids.ids)]
        return action

    def action_view_accounts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chart of Accounts'),
            'res_model': 'account.account',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.account_ids.ids)],
            'context': {'create': False},
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Logs'),
            'res_model': 'aafaq.import.log',
            'view_mode': 'list,form',
            'domain': [('queue_id', '=', self.id)],
        }

    def action_view_existing_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Already Existing Moves'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.existing_move_ids.ids)],
            'context': {'create': False},
        }

    def action_view_updated_partners(self):
        self.ensure_one()
        action = self.env.ref('contacts.action_contacts').read()[0]
        action['name'] = _('Updated Existing Partners')
        action['domain'] = [('id', 'in', self.updated_partner_ids.ids)]
        action['context'] = {'create': False}
        return action

    def action_view_updated_accounts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Updated Existing Accounts'),
            'res_model': 'account.account',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.updated_account_ids.ids)],
            'context': {'create': False},
        }

    
    def action_script_lot(self):
        decoded = base64.b64decode(self.script_att)
        excel_file = io.BytesIO(decoded)
        workbook = load_workbook(filename=excel_file, read_only=True, data_only=True)
        ws = workbook.active
        for row in ws.iter_rows(values_only=True):
            _logger.info("=-=-=script run-=-%s"%(str(row)))
            if row and row[0] and row[0] != 'new lot':
                date_str = row[1].strftime('%d-%m-%Y')
                lot = self.env['stock.lot'].sudo().search([('name', '=', row[0])], limit=1)
                _logger.info("=-=-=lot-=-%s"%(lot))
                if lot:
                    self.env.cr.execute("""UPDATE stock_lot SET create_date = TO_TIMESTAMP(%s, 'DD-MM-YYYY')  WHERE id = %s """, (date_str, lot.id))
                    self.env.cr.commit()
    
    @api.depends('move_ids')
    def _compute_move_count(self):
        for record in self:
            record.move_count = len(record.move_ids)

    @api.depends("move_ids", "move_ids.state")
    def _compute_entry_status(self):
        """Batch-compute via SQL: draft if any linked move is draft, else done if any posted."""
        self.entry_status = False
        queue_ids = self.ids
        if not queue_ids:
            return
        self.env.cr.execute(
            """
                SELECT affaq_queue_id,
                       CASE
                           WHEN BOOL_OR(state = 'draft') THEN 'draft'
                           ELSE 'done'
                       END
                FROM account_move
                WHERE affaq_queue_id = ANY(%s)
                  AND state IN ('draft', 'posted')
                GROUP BY affaq_queue_id
            """,
            [list(queue_ids)],
        )
        status_by_queue = dict(self.env.cr.fetchall())
        for record in self:
            record.entry_status = status_by_queue.get(record.id, False)

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for record in self:
            record.payment_count = len(record.payment_ids)

    def _classify_exception(self, exception):
        from odoo.exceptions import AccessError, MissingError

        if isinstance(exception, ValidationError):
            return "error", "validation"
        if isinstance(exception, UserError):
            return "warning", "user"
        if isinstance(exception, AccessError):
            return "error", "access"
        if isinstance(exception, MissingError):
            return "error", "missing"
        return "error", "system"

    def _append_text_log(self, message):
        self.log = (self.log or "") + f"\n{message}"

    def _create_log(self, message, level="info", error_type=None,
                    row_number=None, record_key=None, model=None, data=None):
        if self.import_source == "email" and level == "error":
            alias_label = self.alias_email or self.alias_config_id.alias_name
            if alias_label:
                message = _("Alias %(alias)s: %(message)s", alias=alias_label, message=message)
        payload = {"payload": str(data)} if data not in (None, False, "") else False
        self.env["aafaq.import.log"].sudo().create({
            "queue_id": self.id,
            "level": level,
            "error_type": error_type,
            "message": message,
            "row_number": row_number,
            "record_key": record_key,
            "model": model,
            "data": payload,
        })

    def safe_get(self, row, header_map, col_name):
        if not col_name:
            return False
        if isinstance(col_name, list):
            if len(col_name) == 0:
                return None
            return "-".join([normalize_col_val(col ,str(row[header_map[col]]).strip()) for col in col_name if col in header_map])
        idx = header_map.get(col_name)
        if idx is None or idx >= len(row):
            return None
        return str(row[idx]).strip() if row[idx] else None

    # ---------------------------
    # Date Parsing
    # ---------------------------
    def parse_date(self, key, value):
        """Convert Excel string/float/datetime into Odoo compatible date."""
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.strptime(value.strip(), "%d/%m/%Y").date()
            except Exception:
                try:
                    return datetime.strptime(value.strip(), "%Y-%m-%d").date()
                except Exception:
                    self.log = (self.log or "") + f"{key}: Invalid date format: {value}. Use dd/mm/yyyy"
        return False

    # ---------------------------
    # Customer / Partner
    # ---------------------------
    def get_customer(self, key, name):
        if not name:
            self.log = (self.log or "") + f"\n{key}: Missing ACCT_NAME."
        partner = self.env["res.partner"].sudo().search([("name", "=", name)], limit=1)
        if not partner:
            raise ValidationError("Customer not found for name :%s" %name)
        return partner

    # ---------------------------
    # Currency and PriceList
    # ---------------------------
    def _get_currency(self, key, code):
        if not code:
            raise ValidationError("Currency code missing. InternalID: %s"%code)
        currency = self.env["res.currency"].sudo().with_context(active_test=False).search([("name", "=", code)], limit=1)
        if not currency:
            raise ValidationError("Currency not found in system for code: %s. InternalID: %s"%(code, key))
            self.log = (self.log or "") + f"\n{key}: "
        if not currency.active:
            currency.write({'active': True})
        return currency

    # ---------------------------
    # Payment Term
    # ---------------------------
    def get_payment_term(self, key, name):
        if not name:
            return False
        term = self.env["account.payment.term"].search([("name", "=", name)], limit=1)
        if not term:
            self.log = (self.log or "") + f"\n{key}: Payment Term {name} not found."
        return term

    # ---------------------------
    # Product
    # ---------------------------
    def get_import_product(self, key, name):
        if not name:
            return self.env['product.product']
        product = self.env["product.product"].search([("name", "=", name)], limit=1)
        if not product and name:
            product = self.env["product.product"].create({
                "name": name,
                "list_price": 0.0,
                "standard_price": 0.0,
                "type": "consu",
                "categ_id": self.env.ref("product.product_category_all").id,
            })
            self.log = (self.log or "") + f"\n{key}: Product {name} CREATED."
        return product

    def get_product(self, key, code, name):
        if not code or not name:
            self.log = (self.log or "") + f"\n{key}: Product code/name missing."
        product = self.env["product.product"].search([
            "|", ("default_code", "=", code), ("name", "=", name)], limit=1)
        if not product and name:
            product = self.env["product.product"].create({
                "name": name,
                "default_code": code,
                "list_price": 0.0,
                "standard_price": 0.0,
                "type": "consu",
                "categ_id": self.env.ref("product.product_category_all").id,
            })
            # self.log = (self.log or "") + f"\n{key}: Product {code, name} CREATED."
        return product

    # ---------------------------
    # Tax
    # ---------------------------
    def _to_float(self, value):
        """Try converting value to float if possible, else return 0.0"""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return 0.0

    def get_taxes(self, key, tax_rate):
        """Expect comma-separated tax names."""
        taxes = self.env["account.tax"]

        tax_rate = self._to_float(tax_rate)
        if not tax_rate:
            return taxes
        tax = self.env["account.tax"].search([("amount", "=", tax_rate),('company_id','=',self.company_id.id)], limit=1)
        if not tax:
            self.log = (self.log or "") + f"\n{key}: Tax {tax_rate} not found."
        taxes |= tax
        return taxes

    # ---------------------------
    # Analytic Account / Distribution
    # ---------------------------
    def get_analytic(self, name):
        if not name:
            return {}
        analytic = self.env["account.analytic.account"].search([("name", "=", name)], limit=1)
        if not analytic:
            analytic = self.env["account.analytic.account"].create({"name": name})
        return {analytic.id: 100}

    def get_file_type(self, file_type):
        if file_type and file_type == "PDF File":
            file_type = "pdf"
        elif file_type and file_type == "JPEG Image":
            file_type = "image"
        elif file_type and file_type == "Excel File":
            file_type = "excel_file"
        else:
            file_type = "other"
        return file_type

    # ---------------------------
    # Check For record already created or not
    # ---------------------------
    def check_move_already_exist(self, key, move_type):
        return self.env['account.move'].sudo().search([
            ('move_type', '=', move_type),
            ('internal_id', '=', key),
            ('state', '!=', 'cancel'),
        ], limit=1)

    def action_view_invoice(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_out_invoice').read()[0]  # Standard Sale Order action
        action['domain'] = [('id', 'in', self.move_ids.ids), ('move_type', '=', 'out_invoice')]
        return action

    def action_view_journal_entries(self):
        self.ensure_one()
        action = {
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'name': _("Imported Journal Entries of %s" % self.name),
            'domain': [('id', 'in', self.move_ids.ids), ('move_type', '=', 'entry')],
            'view_mode': 'list,form',
        }
        return action


    def action_view_bills(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_in_invoice').read()[0]  # Standard Sale Order action
        action['domain'] = [('id', 'in', self.move_ids.ids), ('move_type', '=', 'in_invoice')]
        return action

    # ---------------------------
    # Account Type
    # ---------------------------
    def _get_account_type(self, acc_code):
        """ Map Netsuite account code prefix to Odoo account_type """
        if acc_code.startswith(("113", "140", "141", "146", "147", "148", "150", "180")):
            return "asset_current"
        elif acc_code.startswith(("225", "229")):
            return "liability_current"
            print(account)
        elif acc_code.startswith("300"):
            return "equity"
        elif acc_code.startswith("400"):
            return "income"
        elif acc_code.startswith(("500", "510")):
            return "expense_direct_cost"
        elif acc_code.startswith(("600", "601", "602", "604", "610", "622")):
            return "expense"
        else:
            return "expense"  # fallback to expense (safe default)

    def _get_account(self, account_name, using='name', currency=None):
        """Fetch account (raise if missing)"""
        if using == 'code':
            domain = [('code', '=', account_name)]
        else:
            domain = [('name', '=', account_name)]
        account = self.env["account.account"].sudo().search(domain)
        if len(account) > 1:
            account = account.filtered(lambda a: a.currency_id == currency)[:1]
        if not account:
            raise ValidationError("Account not found for %s: %s" % (using, account_name))
        return account

    def get_journal_id(self, account_name):
        acc_code_raw, acc_name = account_name.split(':', 1)
        acc_code = acc_code_raw.strip().split()[0]
        acc_name = acc_name.strip()
        account = self._get_account(account_name)
        journal_name = acc_name.split(':')[-1].strip()
        journal_code = acc_code[-4:]
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), ('default_account_id', '=', account.id)], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': journal_name,
                'code': journal_code,
                'type': 'bank',
                'default_account_id': account.id,
            })
        return journal

    # ---------------------------
    # Journal Entry Vals
    # ---------------------------
    def prepare_journal_vals(self, key, first_row, header_map, move_type):
        name = "/"
        # exchange_rate = self._to_float(first_row[header_map.get("Exchange Rate")])
        currency = self._get_currency(key, self._get_val(first_row, header_map, "TRAN_CURRENCY"))
        date_idx = header_map.get("VALUE_DATE")
        date = self.parse_date(key, first_row[date_idx] if date_idx is not None else None)
        ref = self._get_val(first_row, header_map, "TRAN_RMKS")

        return {
            "name": name,
            "move_type": move_type,
            "affaq_queue_id": self.id,
            "internal_id": key if self.record_type == "journal_entries" else None,
            "date": date,
            "currency_id": currency.id,
            "journal_id": self.journal_id.id,
            # "exchange_rate": exchange_rate,
            "ref": ref,
            "company_id": self.company_id.id,
            "entry_user": self._get_val(first_row, header_map, "ENTRY_USER_ID"),
            "entry_date": self._get_val(first_row, header_map, "ENTRY_DATE"),
            "transaction_date": self._get_val(first_row, header_map, "TRAN_DATE"),
        }

    def get_default_account(self, row, dt_cr):
        if dt_cr == 'credit':
            return self.company_id.partner_id.with_company(self.company_id or self.env.company).property_account_receivable_id
        else:
            bank_journal = self.env['account.journal'].search(
                domain=[
                    *self.env['account.journal']._check_company_domain(self.company_id.id),
                    ('type', '=', 'bank'),
                ],
                limit=1,
            )
            return bank_journal.default_account_id
    # ---------------------------
    # Journal Entry Line Vals
    # ---------------------------
    def prepare_journal_line_vals(self, key, row, header_map):
        debit = credit = 0
        required_fields = [
            field for field in ["ACCT_NAME", "ACCT_NUM", "GL_SUB_HEAD_DESC"]
            if field in header_map
        ]
        self._check_required_fields(row, header_map, required_fields, key)
        name = self._get_val(row, header_map, "TRAN_PARTICULAR")
        acct_num = self._get_val(row, header_map, "ACCT_NUM")
        gl_desc = self._get_val(row, header_map, "GL_SUB_HEAD_DESC")

        amount = self._to_float(self._get_val(row, header_map, "TRAN_AMT"))
        move_date = self.parse_date(key, self._get_val(row, header_map, "VALUE_DATE"))
        dt_cr = str(self._get_val(row, header_map, "DR_CR_IND") or "").strip().lower()

        company_currency = self.company_id.currency_id
        line_currency = self._get_currency(key, self._get_val(row, header_map, "TRAN_CURRENCY"))

        partner = False
        account_id = False
        tax_tag_ids = []

        # --------------------------------------------------
        # Partner Match
        # --------------------------------------------------
        if acct_num:
            acct_num = str(acct_num).strip()
            partner = self.env['res.partner'].search([
                ('finacle_acct_num', '=', acct_num)
            ], limit=1)

        # --------------------------------------------------
        # Account Logic
        # --------------------------------------------------
        if partner:
            finacle_acct_num = partner.finacle_acct_num or ''
            if finacle_acct_num.startswith('TRY'):
                account_id = partner.account_id
            elif gl_desc:
                account_id = self._get_account(gl_desc.strip(), currency=line_currency)

        if not account_id and acct_num:
            account_id = self._get_account(acct_num, using='code')

        if not account_id:
            raise ValidationError(_("Account not found for ACCT_NUM %s (InternalID: %s)") % (acct_num, key))

        # --------------------------------------------------
        # Analytic Distribution from Partner
        # --------------------------------------------------
        analytic_distribution = {}
        if partner:
            analytic_distribution = partner.get_analytic_distribution()

        # --------------------------------------------------
        # Amount logic
        # --------------------------------------------------
        debit_val = amount if dt_cr in ("debit", "d") else 0.0
        credit_val = amount if dt_cr in ("credit", "c") else 0.0
        foreign_amount = debit_val - credit_val

        vals = {
            "name": name,
            "account_id": account_id.id,
            "transaction_date": move_date,
            "acc_number": acct_num,
            "code_rpt": self._get_val(row, header_map, "RPT_CODE"),
            "ref_num": self._get_val(row, header_map, "REF_NUM"),
            "free_text": self._get_val(row, header_map, "FREE_TEXT"),
            "partner_id": partner.id if partner else False,
            "analytic_distribution": analytic_distribution,
        }

        # --------------------------------------------------
        # Currency handling
        # --------------------------------------------------
        if line_currency == company_currency:
            vals.update({
                "debit": debit_val,
                "credit": credit_val,
            })
        else:
            balance = line_currency._convert(
                foreign_amount,
                company_currency,
                self.company_id,
                move_date
            )

            vals.update({
                "debit": balance if balance > 0 else 0.0,
                "credit": -balance if balance < 0 else 0.0,
                "amount_currency": foreign_amount,
                "currency_id": line_currency.id,
            })

        return vals

    # ---------------------------------------------------------------------------------
    # ---------------------------------------------------------------------------------
    # ---------------------------------------------------------------------------------

    def action_process_queue(self):
        """Entry point – call appropriate processor based on record type"""
        self.ensure_one()
        if self.state not in ["draft","in_progress"]:
            return

        self.log_ids.unlink()
        self.write({
            "state": "in_progress",
            "log": "",
            "existing_move_ids": [(5, 0, 0)],
            "updated_partner_ids": [(5, 0, 0)],
            "updated_account_ids": [(5, 0, 0)],
        })
        header, rows = self._read_file_rows()
        batch_size_param = self.env['ir.config_parameter'].sudo().get_param(
            'importer.batch_size', default=100
        )
        self._schedule_batches(rows, header, batch_size=int(batch_size_param))

    def _whole_file_group_key(self):
        """Stable grouping key when RECORD_KEY_MAP is False (one entry per file)."""
        return self.name or "file"

    def _group_standard_rows(self, rows, header_map):
        filedata = defaultdict(list)

        record_key = RECORD_KEY_MAP.get(self.record_type, None)
        if record_key is False:
            return {self._whole_file_group_key(): list(rows)}

        for row_idx, row in enumerate(rows):
            internal_id = self.safe_get(row, header_map, record_key)
          
            if internal_id in (None, False, ""):
                filedata[str(row_idx)] = row
                continue

            try:
                key = str(int(float(internal_id)))
            except Exception:
                key = str(internal_id)

            filedata[key].append(row)

        return filedata

    # -----------------------------
    # Batch Scheduling
    # -----------------------------
    def _schedule_batches(self, rows, header, batch_size=100):
        self.ensure_one()
        print("Header Map:", header)
        # Map header columns
        header_map = {
            str(h).strip(): idx
            for idx, h in enumerate(header)
            if h and str(h).strip()
        }
        record_key = RECORD_KEY_MAP.get(self.record_type, None)
        # adj_entries: one job for the whole file (so one error can revert all).
        if record_key is False or self.record_type == "adj_entries":
            self.with_delay()._process_batch(list(rows), header_map)
            return
        filedata = self._group_standard_rows(rows, header_map)
        invoice_items = list(filedata.items())
        _logger.info("=-=-=Invoice Items-=-%s"%(invoice_items))
        _logger.info("=-=-=Invoice Items batch size-=-%s"%(batch_size))
        for i in range(0, len(invoice_items), batch_size):
            batch_chunk = invoice_items[i:i + batch_size]
            rows_to_process = []
            for _, batch_rows in batch_chunk:
                if not record_key:
                    rows_to_process.append(batch_rows)
                else:
                    rows_to_process.extend(batch_rows)
            _logger.info("=-=-=process batch-=-%s"%(rows_to_process))
            self.with_delay()._process_batch(rows_to_process, header_map)
            # self._process_batch(rows_to_process, header_map)

    def _prepare_import_batches(self):
        pass

    def _process_batch(self, rows, header_map):
        try:
            if self.record_type in ("journal_entries", "adj_entries"):
                self._create_journal_entries(rows, header_map)
            if self.record_type in ("customer", "customer_wakala_asset", "customer_wakala_lib"):
                self._create_customer_batch(rows, header_map)
            elif self.record_type == "coa":
                self._create_coa_batch(rows, header_map)
            elif self.record_type == "attachment":
                self._create_attachment_record(rows, header_map)
            if self.state != "failed":
                self.state = "done"
        except Exception as e:
            if self.record_type == "adj_entries" and self.move_ids:
                self.move_ids.sudo().unlink()
            self.state = "failed"
            level, error_type = self._classify_exception(e)
            self._create_log(
                message=str(e),
                level=level,
                error_type=error_type,
                model=self._name,
            )

    # -----------------------------
    # File Reader
    # -----------------------------
    def _convert_xls_to_xlsx(self):
        """Convert legacy .xls file into a BytesIO .xlsx stream."""
        try:
            file_data = base64.b64decode(self.file)
            # Read .xls using xlrd
            xls_book = xlrd.open_workbook(file_contents=file_data)
            xls_sheet = xls_book.sheet_by_index(0)

            # Create new .xlsx workbook
            xlsx_book = Workbook()
            xlsx_sheet = xlsx_book.active

            for row_idx in range(xls_sheet.nrows):
                row_values = xls_sheet.row_values(row_idx)
                converted_row = []
                for val in row_values:
                    if isinstance(val, float):
                        try:
                            dt = xlrd.xldate_as_datetime(val, 0)
                            if 1900 < dt.year < 2050:
                                val = dt.date()
                            else:
                                val = int(val) if val.is_integer() else float(val)
                        except Exception:
                            val = int(val) if val.is_integer() else float(val)
                    converted_row.append(val)
                xlsx_sheet.append(converted_row)

            # Save in memory
            xlsx_io = io.BytesIO()
            xlsx_book.save(xlsx_io)
            xlsx_io.seek(0)
            return xlsx_io
        except Exception as e:
            raise ValidationError(f"Failed to convert .xls to .xlsx: {str(e)}")

    def _normalize_xlsx_stream(self, excel_file):
        """Drop a single-cell sheet dimension so openpyxl reads every cell.

        SQL/MIS exports often write ``<dimension ref="A1"/>`` while the sheet
        actually contains many columns. openpyxl's read-only parser trusts that
        range and returns only A1, so the importer sees no data rows. Excel
        rewrites the range on save, which is why the same file works after
        opening it once.
        """
        excel_file.seek(0)
        raw = excel_file.read()
        pattern = re.compile(
            br"<dimension\b[^>]*/>|<dimension\b[^>]*>\s*</dimension>",
            re.IGNORECASE,
        )
        try:
            src = io.BytesIO(raw)
            out = io.BytesIO()
            changed = False
            with zipfile.ZipFile(src) as zin, zipfile.ZipFile(
                out, "w", compression=zipfile.ZIP_DEFLATED
            ) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                        def _strip_single_cell(match):
                            nonlocal changed
                            tag = match.group(0).decode("utf-8", "replace")
                            ref_match = re.search(r'ref="([^"]+)"', tag)
                            ref = (ref_match.group(1) if ref_match else "").upper()
                            parts = ref.split(":") if ref else []
                            single = (not parts) or len(parts) == 1 or parts[0] == parts[-1]
                            if not single:
                                return match.group(0)
                            changed = True
                            return b""

                        data = pattern.sub(_strip_single_cell, data, count=1)
                    zout.writestr(item, data)
            if changed:
                out.seek(0)
                return out
        except zipfile.BadZipFile:
            pass
        excel_file.seek(0)
        return excel_file

    def _iter_excel_rows(self, excel_file):
        """Load all sheet rows, tolerating exports with a broken sheet dimension.

        Some MIS/SQL exports set ``<dimension ref="A1"/>`` even when the sheet
        has many columns. openpyxl ``read_only=True`` then only returns cell A1,
        so no data rows are seen and no queue jobs are scheduled.
        """
        excel_file = self._normalize_xlsx_stream(excel_file)
        excel_file.seek(0)
        workbook = load_workbook(filename=excel_file, read_only=True, data_only=True)
        try:
            ws = workbook.active
            dim = (getattr(ws, "dimensions", None) or "").upper()
            # e.g. "A1" / "A1:A1" → only one cell declared used
            broken_dimension = dim in ("A1", "A1:A1") or (
                dim.startswith("A1") and ":" not in dim
            )
            if not broken_dimension:
                rows = [list(row) for row in ws.iter_rows(values_only=True)]
                # Extra guard: header should have more than one column for our loaders
                if rows and len([c for c in rows[0] if c not in (None, "")]) > 1:
                    return rows
        finally:
            workbook.close()

        excel_file.seek(0)
        workbook = load_workbook(filename=excel_file, read_only=False, data_only=True)
        try:
            ws = workbook.active
            if hasattr(ws, "reset_dimensions"):
                ws.reset_dimensions()
            return [list(row) for row in ws.iter_rows(values_only=True)]
        finally:
            workbook.close()

    def _read_file_rows(self):
        """Return header row and remaining rows from .xls, .xlsx or .csv."""
        self.ensure_one()
        if not self.file:
            raise ValidationError("Please upload a file.")
        filename = self.filename or ""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in IMPORT_FILE_EXTENSIONS:
            raise ValidationError(
                "Unsupported file type: Only .xls, .xlsx or .csv files are supported."
            )

        if ext == ".csv":
            return self._read_csv_rows()

        # Decode
        if ext == ".xlsx":
            decoded = base64.b64decode(self.file)
            excel_file = io.BytesIO(decoded)
        else:
            excel_file = self._convert_xls_to_xlsx()
        try:
            rows = self._iter_excel_rows(excel_file)
            if not rows:
                raise ValidationError("The Excel file is empty.")
            header = rows[0]
            data_rows = [
                row for row in rows[1:]
                if any(cell not in (None, "", " ") for cell in row)
            ]
            if not data_rows:
                raise ValidationError(
                    "No data rows found in the Excel file. "
                    "Check that the first sheet has a header row and data below it."
                )
            return header, data_rows
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to read Excel file: {str(e)}")

    def _read_csv_rows(self):
        decoded = base64.b64decode(self.file)
        text = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = decoded.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValidationError("Failed to decode CSV file.")
        rows = [row for row in csv.reader(io.StringIO(text))]
        if not rows:
            raise ValidationError("The CSV file is empty.")
        header = rows[0]
        data_rows = [
            row for row in rows[1:]
            if any(cell not in (None, "", " ") for cell in row)
        ]
        return header, data_rows

    def check_required_headers(self, required_headers, header_map):
        missing_headers = list(dict.fromkeys([h for h in required_headers if h not in header_map]))
        if missing_headers:
            message = f"Missing required headers: {', '.join(missing_headers)}"
            log = (self.log or "") + f"\n{message}"
            self.write({
                'log': log,
                'state': "failed"
            })
            self._create_log(
                message=message,
                level="error",
                error_type="validation",
                model=self._name,
            )
            return True
        return False

    def get_data(self, rows, header_map, record_key="Internal ID"):
        if record_key is False:
            return {self._whole_file_group_key(): list(rows)}
        data = defaultdict(list)
        for row_idx, row in enumerate(rows):
            internal_id = self.safe_get(row, header_map, record_key)
            if internal_id in (None, False, ""):
                data[str(row_idx)] = row
                continue
            try:
                key = str(internal_id)
            except:
                key = str(internal_id)
            data[key].append(row)
        return data

    # ---------------------------
    # Autobalance | Journal Entries
    # Mirrors account.move._sync_unbalanced_lines / _get_automatic_balancing_account
    # ---------------------------
    def _get_import_balancing_account(self, journal_id=False):
        """Prefer journal default account, else company journal suspense account."""
        self.ensure_one()
        if journal_id:
            journal = self.env["account.journal"].browse(journal_id)
            if journal.default_account_id:
                return journal.default_account_id
        suspense = self.company_id.account_journal_suspense_account_id
        if not suspense:
            raise ValidationError(_(
                "No Journal Suspense Account configured on company %s. "
                "Set it under Accounting settings to allow auto-balancing unbalanced imports."
            ) % self.company_id.display_name)
        return suspense

    def _ensure_journal_entry_balanced(self, journal_lines, journal_vals):
        """
        Journal entries (JV): if prepared lines are unbalanced, append an
        Automatic Balancing Line (same idea as account.move._sync_unbalanced_lines).

        Adjustment entries (AE): raise ValidationError so the unbalanced
        entry is not created.
        """
        if not journal_lines:
            return journal_lines

        company_currency = self.company_id.currency_id
        total_debit = sum(line_vals.get("debit", 0.0) for _, _, line_vals in journal_lines)
        total_credit = sum(line_vals.get("credit", 0.0) for _, _, line_vals in journal_lines)
        # balance needed on balancing line = credit - debit (Odoo convention)
        balance = company_currency.round(total_credit - total_debit)
        if company_currency.is_zero(balance):
            return journal_lines

        if self.record_type == "adj_entries":
            ref = journal_vals.get("internal_id") or journal_vals.get("ref") or ""
            raise ValidationError(_(
                "Unbalanced adjustment entry %(ref)s: debit %(debit)s, "
                "credit %(credit)s, difference %(diff)s. The entry was not created."
            ) % {
                "ref": ref,
                "debit": company_currency.format(total_debit),
                "credit": company_currency.format(total_credit),
                "diff": company_currency.format(abs(balance)),
            })

        account = self._get_import_balancing_account(journal_vals.get("journal_id"))
        currency = self.env["res.currency"].browse(journal_vals.get("currency_id")) or company_currency
        balancing_vals = {
            "name": _("Automatic Balancing Line"),
            "account_id": account.id,
            "balance": balance,
            "currency_id": currency.id,
            "tax_ids": False,
        }
        journal_lines.append((0, 0, balancing_vals))
        return journal_lines

    def _revert_adj_entries(self, moves):
        """adj_entries only: on error, remove any moves already created and mark failed."""
        if self.record_type != "adj_entries":
            return False
        if moves:
            moves.sudo().unlink()
        self.state = "failed"
        return True

    def _warn_future_journal_entry(self, key, move_date):
        """Warn when JV/AE entry date is in a later month than today (same month is allowed)."""
        if self.record_type not in ("journal_entries", "adj_entries"):
            return
        if not move_date:
            return
        today = fields.Date.context_today(self)
        if (move_date.year, move_date.month) <= (today.year, today.month):
            return
        message = _(
            "Future-period entry: VALUE_DATE %(date)s is after the current month "
            "(%(month)s) for InternalID %(key)s."
        ) % {
            "date": move_date,
            "month": today.strftime("%b %Y"),
            "key": key,
        }
        self._append_text_log(message)
        self._create_log(
            message=message,
            level="warning",
            error_type="validation",
            record_key=key,
            model="account.move",
        )

    # ---------------------------
    # Create | Journal Entries
    # ---------------------------
    def _create_journal_entries(self, rows, header_map):
        self.ensure_one()
        required_headers = REQUIRED_HEADERS.get(self.record_type)
        result = self.check_required_headers(required_headers, header_map)
        if result:
            return
        jv_data = self.get_data(rows, header_map, RECORD_KEY_MAP.get(self.record_type))
        jv_ids = self.env["account.move"]
        for key, journal_rows in jv_data.items():
            first_row = journal_rows[0]
            existing_move = self.check_move_already_exist(key, "entry")
            if self.record_type == "journal_entries" and existing_move:
                self.existing_move_ids = [(4, existing_move.id)]
                continue

            journal_vals = self.prepare_journal_vals(key, first_row, header_map, "entry")
            journal_lines = []
            analytic_distribution = {}
            partner_id = False
            for row in journal_rows:
                try:
                    journal_line = self.prepare_journal_line_vals(key, row, header_map)
                    analytic_distribution |= journal_line.pop("analytic_distribution", {})
                    if partner := journal_line.pop("partner_id", False):
                        partner_id = partner
                    if not journal_line:
                        break
                    journal_lines.append((0, 0, journal_line))
                except Exception as e:
                    level, error_type = self._classify_exception(e)
                    message = f"Line Error: {str(e)} : InternalID: {key}"
                    self._append_text_log(message)
                    self._create_log(
                        message=str(e),
                        level=level,
                        error_type=error_type,
                        record_key=key,
                        model="account.move.line",
                        data=row,
                    )
                    if self._revert_adj_entries(jv_ids):
                        return self.env["account.move"]
                    journal_lines = []
                    break

            if not journal_lines:
                continue

            try:
                journal_lines = self._ensure_journal_entry_balanced(journal_lines, journal_vals)
            except (ValidationError, UserError) as e:
                message = e.name if hasattr(e, "name") else str(e)
                self._append_text_log(f"ValidationError: {message} : InternalID: {key}")
                level, error_type = self._classify_exception(e)
                self._create_log(
                    message=message,
                    level=level,
                    error_type=error_type,
                    record_key=key,
                    model="account.move",
                )
                if self._revert_adj_entries(jv_ids):
                    return self.env["account.move"]
                continue

            journal_vals.update({"line_ids": journal_lines})
            try:
                with self.env.cr.savepoint():
                    move = self.env["account.move"].sudo().with_context().create(journal_vals)
                    move.line_ids.write({
                        "analytic_distribution": analytic_distribution,
                        "partner_id": partner_id,
                    })
            except (ValidationError, UserError) as e:
                message = e.name if hasattr(e, "name") else str(e)
                self._append_text_log(f"ValidationError: {message} : InternalID: {key}")
                level, error_type = self._classify_exception(e)
                self._create_log(
                    message=message,
                    level=level,
                    error_type=error_type,
                    record_key=key,
                    model="account.move",
                    data=journal_vals,
                )
                if self._revert_adj_entries(jv_ids):
                    return self.env["account.move"]
                continue
            except Exception as e:
                level, error_type = self._classify_exception(e)
                self._append_text_log(f"Unexpected Error: {str(e)} : InternalID: {key}")
                self._create_log(
                    message=str(e),
                    level=level,
                    error_type=error_type,
                    record_key=key,
                    model="account.move",
                    data=journal_vals,
                )
                if self._revert_adj_entries(jv_ids):
                    return self.env["account.move"]
                continue
            self._warn_future_journal_entry(key, journal_vals.get("date"))
            jv_ids += move

        if self.record_type != "adj_entries":
            try:
                jv_ids._post()
            except Exception as e:
                level, error_type = self._classify_exception(e)
                self._append_text_log(f"Unexpected Error: {str(e)}")
                self._create_log(
                    message=str(e),
                    level=level,
                    error_type=error_type,
                    model="account.move",
                )
        return jv_ids


    def _assign_analytic_tags(self, internal_id, tag_label_map, options):
        valid = True
        for field, (col_name ,label, mandate) in tag_label_map.items():
            if not label:
                continue
            product_map = self.env['product.mapping'].search([
                    ('name', '=', label)
                ], limit=1)
            if not product_map and mandate:
                self._log_row_error(internal_id, f"{col_name} '{label}' not found")
                valid = False
                continue
            if product_map and product_map.analytic_account_ids:
                options[field] = [(6, 0, product_map.analytic_account_ids.ids)]
        return valid
    # ---------------------------
    # Create | Customers
    # ---------------------------
    def _create_customer_batch(self, rows, header_map):
        customer_data = self.get_data(rows, header_map, RECORD_KEY_MAP.get(self.record_type, None))
        record_type = self.record_type
        for key, customer_row in customer_data.items():
            action_create = getattr(self, f'_create_{record_type}', None)
            action_create(customer_row, header_map, key)

    def _create_customer(self, row, header_map,row_index):
        self.ensure_one()

        Partner = self.env['res.partner']
        partner_vals = {}
        required_headers = [
            "ACCT_NAME", "FINACLE_ACCT_NUM",
            "CUSTOMER_TYPE",
            "TYPE_OF_ADVANCE",
            # "SCHEME_DESCRIPTION",
            # "GL_DESC",
            # "GL_SUB_HEAD_CODE",
            # "SCHM_CODE","SEGMENT", "SUBSEGMENT",
        ]
        scm_desc_label = 'SCHEME_DESCRIPTION' if 'SCHEME_DESCRIPTION' in header_map else 'SCHM_DESC'
        tag_label_map = {
            "scheme_analytic_account_ids": (scm_desc_label, self._get_val(row, header_map, scm_desc_label), 1),
            "gl_analytic_account_ids": ("GL_DESC" ,self._get_val(row, header_map, "GL_DESC"), 1),
            "segment_analytic_account_ids": ("SEGMENT", self._get_val(row, header_map, "SEGMENT"), 1),
            "subsegment_analytic_account_ids": ("SUBSEGMENT", self._get_val(row, header_map, "SUBSEGMENT"), 1),
            "adv_type_analytic_account_ids": ("TYPE_OF_ADVANCE", self._get_val(row, header_map, "TYPE_OF_ADVANCE"), 1),
        }
        required_fields = ["ACCT_NAME", "FINACLE_ACCT_NUM", "CUSTOMER_TYPE", "TYPE_OF_ADVANCE"]
        if self.check_required_headers(required_headers, header_map):
            return
        customer_name = self._get_val(row, header_map, "ACCT_NAME")
        finacle_acct_num = self._get_val(row, header_map, "FINACLE_ACCT_NUM")
        cif_id = self._get_val(row, header_map, "CIF_ID")
        internal_id = self._get_val(row, header_map, "FINACLE_ACCT_NUM")
        customer_type = self._get_val(row, header_map, "CUSTOMER_TYPE")
        schm_code = self._get_val(row, header_map, "SCHM_CODE")
        scheme_description = self._get_val(row, header_map, scm_desc_label)
        gl_sub_head_code = self._get_val(row, header_map, "GL_SUB_HEAD_CODE")
        gl_desc = self._get_val(row, header_map, "GL_DESC")
        
        # product_mapping_tag_ids = self._get_val(row, header_map, "TYPE_OF_ADVANCE")
        if self._check_required_fields(row, header_map, required_fields, row_index):
            return True
        partner_vals.update({
            'schm_code': schm_code,
            'finacle_acct_num': finacle_acct_num,
            'gl_sub_head_code': gl_sub_head_code,
            'gl_desc': gl_desc,
            'internal_id': internal_id
        })
        valid = self._assign_analytic_tags(row_index ,tag_label_map, partner_vals)
        if not valid:
            return Partner
        partner = Partner.search([('finacle_acct_num', '=', internal_id)], limit=1)
        if partner:
            partner_vals['customer_type'] = self.record_type
            partner.with_context(use_import=True).write(partner_vals)
            self.updated_partner_ids = [(4, partner.id)]
        else:
            partner_vals.update({
                'name': customer_name,
                'customer_rank': 1,
                'ref': cif_id,
                'aafaq_queue_id': self.id,
                'company_type': COMPANY_TYPE_MAP.get(customer_type),
                'customer_type': self.record_type,
            })
            partner = Partner.sudo().create(partner_vals)
            self._approve_imported_partner(partner)
        return partner

    def _create_customer_wakala_asset(self, row, header_map,row_index):
        self.ensure_one()

        Partner = self.env['res.partner']
        partner_vals = {}
        required_headers = ["CUSTOMER_NAME", "DEAL_NUMBER", "CIF_ID", "CUSTOMER_TYPE", "SCHM_DESC", "CURRENCY_CODE"]
        tag_label_map = {
            "scheme_analytic_account_ids": ("SCHM_DESC", self._get_val(row, header_map, "SCHM_DESC"), 1),
        }
        required_fields = ["CUSTOMER_NAME", "DEAL_NUMBER", "CUSTOMER_TYPE", "CURRENCY_CODE"]
        if self.check_required_headers(required_headers, header_map):
            return
        customer_name = self._get_val(row, header_map, "CUSTOMER_NAME")
        customer_type = self._get_val(row, header_map, "CUSTOMER_TYPE")
        finacle_acct_num = self._get_val(row, header_map, "DEAL_NUMBER")
        cif_id = self._get_val(row, header_map, "CIF_ID")
        internal_id = self._get_val(row, header_map, "DEAL_NUMBER")
        schm_code = self._get_val(row, header_map, "SCHM_CODE")
        currency_code = self._get_val(row, header_map, "CURRENCY_CODE")

        if self._check_required_fields(row, header_map, required_fields, row_index):
            return True
        account_id = self.env['currency.account.mapping'].sudo().get_account_by_currency_code(currency_code, self.record_type)
        if not account_id:
            self._log_row_error(internal_id, f"Account not found for Currency Code: '{currency_code}'")
            return
        partner_vals.update({
            'internal_id': internal_id,
            'schm_code': schm_code,
            'finacle_acct_num': finacle_acct_num,
            'currency_code': currency_code,
            'account_id': account_id
        })
        valid = self._assign_analytic_tags(row_index ,tag_label_map, partner_vals)
        if not valid:
            return Partner
        partner = Partner.search([('finacle_acct_num', '=', internal_id)], limit=1)
        if partner:
            partner_vals['customer_type'] = self.record_type
            partner.with_context(use_import=True).write(partner_vals)
            self.updated_partner_ids = [(4, partner.id)]
        else:
            partner_vals.update({
                'name': customer_name,
                'ref': cif_id,
                'aafaq_queue_id': self.id,
                'company_type': COMPANY_TYPE_MAP.get(customer_type),
                'customer_type': self.record_type,
            })
            partner = Partner.sudo().create(partner_vals)
            self._approve_imported_partner(partner)
        return partner

    def _create_customer_wakala_lib(self, row, header_map, row_index):
        self.ensure_one()

        Partner = self.env['res.partner']
        partner_vals = {}
        required_headers = [
            "ACCT_NAME", "ACCT_NUM", "CIF_ID",
            "SCHEME_DESCRIPTION", "GL_SUB_HEAD_CODE",
            "WAKALA_TYPE", "CURRENCY"
        ]
        tag_label_map = {
            "scheme_analytic_account_ids": ("SCHEME_DESCRIPTION", self._get_val(row, header_map, "SCHEME_DESCRIPTION"), 0),
            "gl_analytic_account_ids": ("WAKALA_TYPE" ,self._get_val(row, header_map, "WAKALA_TYPE"), 0),
            "adv_type_analytic_account_ids": ("GL_DESC", self._get_val(row, header_map, "GL_DESC"), 1),
        }
        required_fields = ["ACCT_NAME", "ACCT_NUM", "CURRENCY"]
        if self.check_required_headers(required_headers, header_map):
            return
        customer_name = self._get_val(row, header_map, "ACCT_NAME")
        # internal_id = self._get_val(row, header_map, "Internal ID")
        finacle_acct_num = self._get_val(row, header_map, "ACCT_NUM")
        cif_id = self._get_val(row, header_map, "CIF_ID")
        internal_id = self._get_val(row, header_map, "ACCT_NUM")
        # customer_type = self._get_val(row, header_map, "CUSTOMER_TYPE")
        schm_code = self._get_val(row, header_map, "SCHM_CODE")
        gl_sub_head_code = self._get_val(row, header_map, "GL_SUB_HEAD_CODE")
        currency_code = self._get_val(row, header_map, "CURRENCY")
        # product_mapping_tag_ids = self._get_val(row, header_map, "GL_DESC")
        if self._check_required_fields(row, header_map, required_fields, row_index):
            return True
        account_id = self.env['currency.account.mapping'].sudo().get_account_by_currency_code(currency_code, self.record_type)
        if not account_id:
            self._log_row_error(internal_id, f"Account not found for Currency Code: '{currency_code}'")
            return
        partner_vals.update({
            'internal_id': internal_id,
            'schm_code': schm_code,
            'finacle_acct_num': finacle_acct_num,
            'gl_sub_head_code': gl_sub_head_code,
            'currency_code': currency_code,
            'account_id': account_id
        })
        valid = self._assign_analytic_tags(row_index ,tag_label_map, partner_vals)
        if not valid:
            return Partner
        partner = Partner.search([('finacle_acct_num', '=', internal_id)], limit=1)
        if partner:
            partner_vals['customer_type'] = self.record_type
            partner.with_context(use_import=True).write(partner_vals)
            self.updated_partner_ids = [(4, partner.id)]
        else:
            partner_vals.update({
                'name': customer_name,
                'customer_rank': 1,
                'ref': cif_id,
                'aafaq_queue_id': self.id,
                'company_type': 'company',
                'customer_type': self.record_type,
            })
            partner = Partner.sudo().create(partner_vals)
            self._approve_imported_partner(partner)
        return partner

    def _approve_imported_partner(self, partner):
        """Mark a newly imported partner as approved when vendor approval is installed."""
        if partner and hasattr(partner, "action_approve_vendor"):
            partner.sudo().action_approve_vendor()

    def _normalize_header(self, val):
        if not val:
            return ""

        val = str(val)
        val = val.replace("\xa0", " ")
        val = val.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        val = re.sub(r'[^a-zA-Z0-9 ]', ' ', val)

        return " ".join(val.strip().lower().split())

    def _get_val(self, row, header_map, key):
        idx = header_map.get(key)
        if idx is None or idx >= len(row):
            return False
        val = row[idx]
        if val in (None, "", " "):
            return False
        if isinstance(val, datetime):
            return val
        return str(val).strip()

    def _log_row_error(self, row_index, message):
        log = (self.log or "") + f"\nRow {row_index}: {message}"
        self.write({
            'log': log,
            # 'state': "failed"
        })
        self._create_log(
            message=message,
            level="error",
            error_type="validation",
            row_number=row_index if isinstance(row_index, int) else False,
            record_key=str(row_index) if row_index not in (None, False, "") else False,
            model=self._name,
        )
        return True    

    def _check_required_fields(self, row, header_map, required_fields, row_index):
        """
        required_fields: list of column names (strings)
        """
        has_error = False

        for field_name in required_fields:
            value = self._get_val(row, header_map, field_name)

            if not value or not str(value).strip():
                self._log_row_error(row_index, f"'{field_name}' is required")
                has_error = True

        return has_error

    def _ungroup_import_row(self, grouped):
        if grouped and isinstance(grouped, (list, tuple)) and grouped and isinstance(grouped[0], (list, tuple)):
            return grouped[-1]
        return grouped

    def _normalize_coa_code(self, value):
        if not value:
            return False
        value = str(value).strip()
        try:
            as_float = float(value)
            if as_float.is_integer():
                return str(int(as_float))
        except (ValueError, TypeError):
            pass
        return value

    def _map_coa_account_type(self, odoo_type):
        if not odoo_type:
            return False
        label = str(odoo_type).strip()
        mapped = COA_ACCOUNT_TYPE_MAP.get(label.lower())
        if mapped:
            return mapped
        valid_types = {
            key for key, _label in self.env["account.account"]._fields["account_type"].selection
        }
        technical = label.lower().replace(" ", "_").replace("-", "_")
        if technical in valid_types:
            return technical
        return False

    def _parse_coa_float(self, value):
        if value in (None, False, ""):
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except (ValueError, TypeError):
            return None

    def _assign_coa_studio_fields(self, Account, vals, row_index, sol_desc, fs_grouping):
        """Map template columns onto Studio fields on account.account."""
        mapping = (
            ("x_studio_sol_desc", sol_desc, "SOL Desc"),
            ("x_studio_fs_grouping", fs_grouping, "FS Grouping"),
        )
        for field_name, value, column in mapping:
            if value in (None, False, ""):
                continue
            field = Account._fields.get(field_name)
            if not field:
                self._log_row_error(
                    row_index,
                    _("Studio field '%s' is missing on Chart of Accounts; cannot map '%s'.")
                    % (field_name, column),
                )
                continue
            converted = self._convert_coa_studio_value(Account, field, value, row_index, column)
            if converted is not None:
                vals[field_name] = converted

    def _convert_coa_studio_value(self, Account, field, value, row_index, column):
        if field.type in ("char", "text", "html"):
            return str(value).strip()
        if field.type in ("float", "monetary"):
            parsed = self._parse_coa_float(value)
            if parsed is None:
                self._log_row_error(
                    row_index,
                    _("'%s' must be a number, got '%s'.") % (column, value),
                )
                return None
            return parsed
        if field.type == "integer":
            parsed = self._parse_coa_float(value)
            if parsed is None:
                self._log_row_error(
                    row_index,
                    _("'%s' must be a number, got '%s'.") % (column, value),
                )
                return None
            return int(parsed)
        if field.type == "selection":
            selection = field.selection
            if callable(selection):
                selection = selection(Account)
            by_key = {str(key): key for key, _label in selection or []}
            by_label = {str(label).strip().lower(): key for key, label in selection or []}
            if value in by_key:
                return by_key[value]
            mapped = by_label.get(str(value).strip().lower())
            if mapped is not None:
                return mapped
            self._log_row_error(
                row_index,
                _("Value '%s' is not a valid option for %s.") % (value, column),
            )
            return None
        if field.type == "many2one":
            comodel = self.env[field.comodel_name].sudo()
            record = comodel.search([("name", "=", value)], limit=1)
            if record:
                return record.id
            self._log_row_error(
                row_index,
                _("No matching record for %s value '%s'.") % (column, value),
            )
            return None
        return value

    def _create_coa_batch(self, rows, header_map):
        self.ensure_one()
        required_headers = REQUIRED_HEADERS.get(self.record_type)
        if self.check_required_headers(required_headers, header_map):
            return
        coa_data = self.get_data(rows, header_map, RECORD_KEY_MAP.get(self.record_type))
        for key, grouped in coa_data.items():
            self._create_coa_account(self._ungroup_import_row(grouped), header_map, key)

    def _create_coa_account(self, row, header_map, row_index):
        self.ensure_one()
        required_fields = ["Currency", "Code", "Account Name", "Odoo Type", "FS Grouping"]
        if self._check_required_fields(row, header_map, required_fields, row_index):
            return self.env["account.account"]

        code = self._normalize_coa_code(self._get_val(row, header_map, "Code"))
        name = self._get_val(row, header_map, "Account Name")
        odoo_type_label = self._get_val(row, header_map, "Odoo Type")
        currency_code = self._get_val(row, header_map, "Currency")
        sol_desc = self._get_val(row, header_map, "SOL Desc")
        fs_grouping = self._parse_coa_float(self._get_val(row, header_map, "FS Grouping"))
        if fs_grouping is None:
            self._log_row_error(row_index, _("'FS Grouping' must be a number"))
            return self.env["account.account"]

        account_type = self._map_coa_account_type(odoo_type_label)
        if not account_type:
            self._log_row_error(
                row_index,
                _("Unknown Odoo Type '%s'. Use a Chart of Accounts type such as Expenses, Receivable, or Bank and Cash.")
                % odoo_type_label,
            )
            return self.env["account.account"]

        currency = False
        if currency_code:
            try:
                currency = self._get_currency(row_index, currency_code)
            except Exception as exc:
                self._log_row_error(row_index, str(exc))
                return self.env["account.account"]

        Account = (
            self.env["account.account"]
            .with_company(self.company_id)
            .with_context(
                allowed_company_ids=[self.company_id.id],
                active_test=False,
            )
            .sudo()
        )
        account = Account.search([("code", "=", code)], limit=1)

        vals = {
            "name": name,
            "account_type": account_type,
            "code": code,
        }
        if currency:
            vals["currency_id"] = currency.id
        self._assign_coa_studio_fields(Account, vals, row_index, sol_desc, fs_grouping)

        if account:
            if not account.active:
                vals["active"] = True
            account.write(vals)
            self.updated_account_ids = [(4, account.id)]
            return account

        vals.update({
            "company_ids": [(6, 0, [self.company_id.id])],
            "aafaq_queue_id": self.id,
        })
        return Account.create(vals)
