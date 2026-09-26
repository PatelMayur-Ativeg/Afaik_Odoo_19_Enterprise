from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def write(self, vals):
        print("WWWWWWWW------------")
        res = super(ProductTemplate, self).write(vals)
        for rec in self: 
            for line in rec.seller_ids:
                vend_prod_rec=self.env['vendor.product'].sudo().search([('partner_supplier_id','=',line.id)])
                if vend_prod_rec:
                    vend_prod = vend_prod_rec.update({
                        'partner_prod_id' :line.partner_id.id,
                        'partner_supplier_id':line.id,
                        'product_id' : rec.id,
                        'minimum_qty' : line.min_qty,
                        'price' : line.price,
                        'delivery_lead_time' : line.delay,
                    })
                else:
                    vals=self.env['vendor.product'].create({
                        'partner_prod_id' :line.partner_id.id,
                        'partner_supplier_id':line.id,
                        'product_id' : rec.id,
                        'minimum_qty' : line.min_qty,
                        'price' : line.price,
                        'delivery_lead_time' : line.delay,
                    })
        return res
