odoo.define('branch.pos_extended',[], function (require) {
    var models = require('point_of_sale.models');
    var _super_posmodel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        initialize: function (session, attributes) {
            var session_model = _.find(this.models, function(model){ return model.model === 'pos.session';});
            session_model.fields.push('branch_id');
            return _super_posmodel.initialize.call(this, session, attributes);
        },

    });
});
