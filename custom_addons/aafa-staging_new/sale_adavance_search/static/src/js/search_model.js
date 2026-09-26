/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SearchModel } from "@web/search/search_model";
import { session } from "@web/session";

function getConfiguredFields(resModel) {
    const mapping = session.advanced_search_config || {};
    return mapping[resModel] || [];
}

patch(SearchModel.prototype, {
    addAutoCompletionValues(searchItemId, autocompleteValue) {
        const searchItem = this.searchItems[searchItemId];
        const fieldName = searchItem && searchItem.fieldName;
        const configuredFields = getConfiguredFields(this.resModel);
        if (
            fieldName &&
            configuredFields.includes(fieldName) &&
            autocompleteValue &&
            typeof autocompleteValue.value === "string"
        ) {
            const searchList = autocompleteValue.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean);
            if (searchList.length > 1) {
                const firstOne = searchList.shift();
                Object.assign(autocompleteValue, {
                    label: firstOne,
                    operator: autocompleteValue.operator,
                    value: firstOne,
                });
                searchList.forEach((searchValue) => {
                    this.query.push({
                        searchItemId,
                        autocompleteValue: {
                            label: searchValue,
                            operator: autocompleteValue.operator,
                            value: searchValue,
                        },
                    });
                });
            }
        }
        super.addAutoCompletionValues(...arguments);
    },
});
