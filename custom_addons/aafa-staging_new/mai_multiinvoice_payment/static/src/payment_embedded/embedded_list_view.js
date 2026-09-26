import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class PaymentEmbeddedListController extends ListController {
    static template = "mai_multiinvoice_payment.PaymentEmbeddedListController";

    /**
     * Embedded lists save independently of the payment form, so the parent
     * compute for excess_amount never runs. Push the server value after save.
     */
    async onRecordSaved(record) {
        await super.onRecordSaved(record);
        if (!record.resId) {
            return;
        }
        const orm = this.orm.silent || this.orm;
        const result = await orm.call(
            "account.payment.invoice",
            "action_get_payment_excess",
            [[record.resId]]
        );
        this.env.bus.trigger("mai-payment-lines-updated", {
            excess_amount: result?.excess_amount,
        });
    }
}

export class PaymentEmbeddedListModel extends listView.Model {
    setup(params, services) {
        super.setup(params, services);
        this.storedDomainString = null;
    }

    /**
     * Avoid refetching embedded lines on every form re-render when the domain is unchanged.
     */
    async load(params = {}) {
        const currentDomain = params.domain?.toString() || "";
        if (currentDomain !== this.storedDomainString) {
            this.storedDomainString = currentDomain;
            return super.load(params);
        }
    }
}

export const PaymentEmbeddedListView = {
    ...listView,
    Controller: PaymentEmbeddedListController,
    Model: PaymentEmbeddedListModel,
};
