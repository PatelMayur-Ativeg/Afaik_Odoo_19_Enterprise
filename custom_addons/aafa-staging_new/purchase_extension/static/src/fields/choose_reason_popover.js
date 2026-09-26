import { registry } from "@web/core/registry";
import { usePopover } from "@web/core/popover/popover_hook";
import { Component } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class ChooseReasonPopover extends Component {
    static template = "purchase_extension.ChooseReasonPopover";
    static props = {
        reason: { type: String },
        close: Function,
    };
}

export class ChooseReasonWidget extends Component {
    static components = { Popover: ChooseReasonPopover };
    static template = "purchase_extension.ChooseReasonWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.popover = usePopover(this.constructor.components.Popover, {
            position: "left",
            popoverClass: "o_choose_reason_popover",
        });
    }

    get reason() {
        return this.props.record.data.choose_reason || "";
    }

    showPopup(ev) {
        if (!this.reason) {
            return;
        }
        this.popover.open(ev.currentTarget, {
            reason: this.reason,
        });
    }
}

export const chooseReasonWidget = {
    component: ChooseReasonWidget,
    fieldDependencies: [{ name: "choose_reason", type: "text" }],
};

registry.category("view_widgets").add("choose_reason_popover", chooseReasonWidget);
