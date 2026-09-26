/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { Many2One } from "@web/views/fields/many2one/many2one";

function canCreateEditFromM2O() {
    return Boolean(user.isAdmin);
}

patch(Many2One.prototype, {
    get activeActions() {
        const actions = super.activeActions;
        if (canCreateEditFromM2O()) {
            return actions;
        }
        return {
            ...actions,
            create: false,
            createEdit: false,
            write: false,
        };
    },

    get many2XAutocompleteProps() {
        const props = super.many2XAutocompleteProps;
        if (!canCreateEditFromM2O()) {
            props.quickCreate = null;
        }
        return props;
    },
});
