import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { PaymentEmbeddedViewEmbedder } from "./view_embedder";
import { Component, onWillUnmount } from "@odoo/owl";

export class PaymentEmbeddedListWidget extends Component {
    static template = "mai_multiinvoice_payment.PaymentEmbeddedListWidget";
    static components = { PaymentEmbeddedViewEmbedder };
    static props = {
        ...standardWidgetProps,
        o2mField: { type: String },
        inverseField: { type: String },
        title: { type: String, optional: true },
    };

    setup() {
        this._onLinesUpdated = (ev) => {
            this._applyExcessAmount(ev.detail?.excess_amount);
        };
        this.env.bus.addEventListener("mai-payment-lines-updated", this._onLinesUpdated);
        onWillUnmount(() => {
            this.env.bus.removeEventListener("mai-payment-lines-updated", this._onLinesUpdated);
        });
    }

    get paymentRecord() {
        return this.props.record;
    }

    get canShowEmbeddedList() {
        return Boolean(this.paymentRecord.resId);
    }

    get embedKey() {
        const payment = this.paymentRecord;
        const field = payment.data[this.props.o2mField];
        const ids = [...(field?.currentIds || [])]
            .filter((id) => typeof id === "number")
            .sort((a, b) => a - b)
            .join(",");
        const partnerId = payment.data.partner_id?.id || 0;
        const currencyId = payment.data.currency_id?.id || 0;
        const state = payment.data.state || "draft";
        return `${payment.resId}-${this.props.inverseField}-${partnerId}-${currencyId}-${state}-${ids}`;
    }

    get viewProps() {
        const payment = this.paymentRecord;
        const domain = this._getDomain();
        return {
            type: "list",
            noBreadcrumbs: true,
            resModel: "account.payment.invoice",
            searchMenuTypes: ["filter", "favorite"],
            domain,
            context: {
                ...payment.context,
                mai_payment_embedded: true,
                list_view_ref: "mai_multiinvoice_payment.view_account_payment_invoice_list_embedded",
                search_view_ref: "mai_multiinvoice_payment.view_account_payment_invoice_search",
            },
            allowSelectors: false,
            searchViewId: false,
            loadIrFilters: true,
            display: {
                controlPanel: true,
            },
        };
    }

    _getDomain() {
        const payment = this.paymentRecord;
        const field = payment.data[this.props.o2mField];
        const lineIds = (field?.currentIds || []).filter((id) => typeof id === "number");
        if (lineIds.length) {
            return [["id", "in", lineIds]];
        }
        if (payment.resId) {
            return [[this.props.inverseField, "=", payment.resId]];
        }
        return [["id", "=", false]];
    }

    _applyExcessAmount(excessAmount) {
        if (excessAmount === undefined) {
            return;
        }
        const payment = this.paymentRecord;
        if (!payment?.data) {
            return;
        }
        payment.data.excess_amount = excessAmount;
        if (payment._values) {
            payment._values.excess_amount = excessAmount;
        }
        payment.model.notify();
    }
}

export const paymentEmbeddedListWidget = {
    component: PaymentEmbeddedListWidget,
    extractProps: ({ attrs }) => ({
        o2mField: attrs.o2m_field,
        inverseField: attrs.inverse_field,
        title: attrs.title || _t("Lines"),
    }),
    fieldDependencies: [
        { name: "state", type: "selection" },
        { name: "partner_id", type: "many2one" },
        { name: "currency_id", type: "many2one" },
        { name: "payment_type", type: "selection" },
        { name: "partner_type", type: "selection" },
        { name: "payment_invoice_ids", type: "one2many" },
        { name: "payment_reversal_ids", type: "one2many" },
        { name: "excess_amount", type: "monetary" },
        { name: "amount", type: "monetary" },
    ],
};

registry.category("view_widgets").add("mai_payment_embedded_list", paymentEmbeddedListWidget);
