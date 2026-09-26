import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { PaymentEmbeddedListView } from "./embedded_list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

const ROW_MOVE_MS = 280;

export class PaymentInvoiceEmbeddedListRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this._togglingIds = new Set();
    }

    /** Same condition as readonly on the checked field in the list view XML. */
    _isLineReadonly(record) {
        const { payment_id, payment_state, payment_reverse_id, reverse_payment_state } =
            record.data;
        return (
            (payment_id && payment_state !== "draft") ||
            (payment_reverse_id && reverse_payment_state !== "draft")
        );
    }

    getRowClass(record) {
        const classes = super.getRowClass(record);
        const extra = [];
        if (record.data.checked) {
            extra.push("table-info");
        }
        if (this._isLineReadonly(record)) {
            extra.push("mai_payment_line_locked");
        }
        return extra.length ? `${classes} ${extra.join(" ")}` : classes;
    }

    /**
     * Keep the checkbox as a static list formatter even while another cell is
     * being edited, so BooleanField cannot write `checked` directly.
     */
    canUseFormatter(column, record) {
        if (column.name === "checked") {
            return true;
        }
        return super.canUseFormatter(column, record);
    }

    /**
     * Capture clicks on the checked cell before the boolean checkbox swallows them.
     * Row clicks no longer toggle selection.
     */
    onClickCapture(record, ev) {
        super.onClickCapture(record, ev);
        const cell = ev.target.closest("td[name='checked']");
        if (!cell || !ev.currentTarget.contains(cell)) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        if (this._isLineReadonly(record) || !record.resId || this._togglingIds.has(record.resId)) {
            return;
        }
        this._toggleLine(record);
    }

    async onCellClicked(record, column, ev) {
        if (column.name === "checked") {
            return;
        }
        return super.onCellClicked(record, column, ev);
    }

    async _toggleLine(record) {
        this._togglingIds.add(record.resId);
        const nextChecked = !record.data.checked;
        const nextReconcile = nextChecked ? record.data.residual : 0;
        const nextSequence = this._nextSequence(record, nextChecked);
        const firstRects = this._captureRowRects();

        this._applyLocalValues(record, {
            checked: nextChecked,
            reconcile_amount: nextReconcile,
            residual_reconcile: nextReconcile,
            sequence: nextSequence,
        });
        this._refreshReconcileAggregate();
        this._moveRecord(record, nextChecked ? 0 : this.props.list.records.length - 1);
        this.props.list.model.notify();
        await this._playRowMove(firstRects);

        try {
            const orm = this.orm.silent || this.orm;
            const result = await orm.call(
                "account.payment.invoice",
                "action_toggle_checked",
                [[record.resId]]
            );
            const lineVals = (result?.lines || []).find((line) => line.id === record.resId);
            if (lineVals) {
                this._applyLocalValues(record, {
                    checked: lineVals.checked,
                    reconcile_amount: lineVals.reconcile_amount,
                    residual_reconcile: lineVals.residual_reconcile,
                    sequence: lineVals.sequence,
                });
                this._refreshReconcileAggregate();
                this.props.list.model.notify();
            }
            this.env.bus.trigger("mai-payment-lines-updated", {
                excess_amount: result?.excess_amount,
            });
        } catch (error) {
            if (this.props.list.model.storedDomainString !== undefined) {
                this.props.list.model.storedDomainString = null;
            }
            await this.props.list.load();
            throw error;
        } finally {
            this._togglingIds.delete(record.resId);
        }
    }

    _nextSequence(record, nextChecked) {
        const siblings = this.props.list.records.filter((rec) => rec !== record);
        if (nextChecked) {
            const otherChecked = siblings.filter((rec) => rec.data.checked);
            if (otherChecked.length) {
                return Math.min(...otherChecked.map((rec) => rec.data.sequence || 0)) - 10;
            }
            return 10;
        }
        const otherUnchecked = siblings.filter((rec) => !rec.data.checked);
        if (otherUnchecked.length) {
            return Math.max(...otherUnchecked.map((rec) => rec.data.sequence || 0)) + 10;
        }
        return 1000;
    }

    _applyLocalValues(record, values) {
        Object.assign(record.data, values);
        if (record._values) {
            Object.assign(record._values, values);
        }
        if (record._changes) {
            for (const fieldName of Object.keys(values)) {
                delete record._changes[fieldName];
            }
        }
        // Re-evaluate modifiers (reconcile_amount is readonly while unchecked).
        if (typeof record._setEvalContext === "function") {
            record._setEvalContext();
        }
    }

    _refreshReconcileAggregate() {
        const list = this.props.list;
        if (!list.aggregates || !("reconcile_amount" in list.aggregates)) {
            return;
        }
        list.aggregates.reconcile_amount = list.records.reduce(
            (sum, rec) => sum + (rec.data.reconcile_amount || 0),
            0
        );
    }

    _moveRecord(record, toIndex) {
        const records = this.props.list.records;
        const fromIndex = records.indexOf(record);
        if (fromIndex < 0 || fromIndex === toIndex) {
            return;
        }
        records.splice(fromIndex, 1);
        records.splice(toIndex, 0, record);
    }

    _getTableBody() {
        return (
            this.tableRef?.el?.querySelector("tbody") ||
            this.rootRef?.el?.querySelector("tbody") ||
            this.el?.querySelector("tbody")
        );
    }

    _captureRowRects() {
        const tbody = this._getTableBody();
        const rowEls = [...(tbody?.querySelectorAll("tr.o_data_row") || [])];
        const firstRects = new Map();
        this.props.list.records.forEach((rec, index) => {
            const row = rowEls[index];
            if (row) {
                firstRects.set(rec.resId, row.getBoundingClientRect());
            }
        });
        return firstRects;
    }

    async _playRowMove(firstRects) {
        if (!firstRects.size) {
            return;
        }
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            return;
        }
        const tbody = this._getTableBody();
        const rowEls = [...(tbody?.querySelectorAll("tr.o_data_row") || [])];
        this.props.list.records.forEach((rec, index) => {
            const row = rowEls[index];
            const first = firstRects.get(rec.resId);
            if (!row || !first) {
                return;
            }
            const last = row.getBoundingClientRect();
            const dy = first.top - last.top;
            if (Math.abs(dy) < 1) {
                return;
            }
            row.classList.add("mai_payment_row_moving");
            row.style.transform = `translateY(${dy}px)`;
            row.style.transition = "none";
            requestAnimationFrame(() => {
                row.style.transition = `transform ${ROW_MOVE_MS}ms ease`;
                row.style.transform = "";
            });
            window.setTimeout(() => {
                row.classList.remove("mai_payment_row_moving");
                row.style.transition = "";
                row.style.transform = "";
            }, ROW_MOVE_MS + 40);
        });
    }
}

export const PaymentInvoiceEmbeddedListView = {
    ...PaymentEmbeddedListView,
    Renderer: PaymentInvoiceEmbeddedListRenderer,
};

registry.category("views").add("mai_payment_invoice_embedded_list", PaymentInvoiceEmbeddedListView);
