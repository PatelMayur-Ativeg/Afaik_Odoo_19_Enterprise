import { View } from "@web/views/view";
import { Component, useSubEnv } from "@odoo/owl";

/**
 * Embeds a full list view (with SearchModel / control panel) inside the payment form.
 * Isolate config so the parent payment form does not leak view switcher / breadcrumbs.
 */
export class PaymentEmbeddedViewEmbedder extends Component {
    static template = "mai_multiinvoice_payment.PaymentEmbeddedViewEmbedder";
    static components = { View };
    static props = {
        viewProps: { type: Object },
        embedKey: { type: String },
    };

    setup() {
        useSubEnv({
            config: {},
        });
    }
}
