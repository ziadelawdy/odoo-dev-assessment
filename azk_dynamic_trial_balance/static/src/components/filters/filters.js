import { _t } from "@web/core/l10n/translation";
import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

/**
 * Filter bar of the Dynamic Trial Balance: the wizard options as switches,
 * editable directly in the report. Every change updates the report options
 * and reloads the report (same mechanism as the native filters).
 */
export class AzkTrialBalanceFilters extends AccountReportFilters {
    static template = "azk_dynamic_trial_balance.TrialBalanceFilters";

    get azkOptions() {
        return this.controller.cachedFilterOptions();
    }

    get azkTb() {
        return this.azkOptions.azk_tb || {};
    }

    get azkHierarchyAvailable() {
        return Boolean(this.azkOptions.display_hierarchy_filter);
    }

    get azkSwitches() {
        const options = this.azkOptions;
        const tb = this.azkTb;
        const switches = [
            { key: "all_entries", label: _t("Unposted Entries"), value: Boolean(options.all_entries), path: "all_entries" },
        ];
        if (this.azkHierarchyAvailable) {
            switches.push(
                { key: "hierarchy", label: _t("Hierarchy and Subtotals"), value: Boolean(options.hierarchy), path: "hierarchy" },
                { key: "only_parents", label: _t("Only Parents"), value: Boolean(tb.account_level) },
            );
        }
        switches.push(
            { key: "skip_zero_balance", label: _t("Skip Zero Balance"), value: Boolean(tb.skip_zero_balance), path: "azk_tb.skip_zero_balance" },
            { key: "show_amount_currency", label: _t("Amount Currency"), value: Boolean(tb.show_amount_currency), path: "azk_tb.show_amount_currency" },
        );
        return switches;
    }

    get azkLevels() {
        return [1, 2, 3, 4, 5];
    }

    get azkPrefixes() {
        return (this.azkTb.account_prefixes || []).join(", ");
    }

    async azkToggle(item) {
        if (item.key === "only_parents") {
            if (item.value) {
                await this.filterClicked({ optionKey: "azk_tb.account_level", optionValue: false, reload: true });
            } else {
                // a level only makes sense on the account tree
                await this.controller.updateOption("hierarchy", true);
                await this.filterClicked({ optionKey: "azk_tb.account_level", optionValue: 1, reload: true });
            }
            return;
        }
        await this.filterClicked({ optionKey: item.path, optionValue: !item.value, reload: true });
    }

    async azkSetLevel(ev) {
        await this.filterClicked({ optionKey: "azk_tb.account_level", optionValue: parseInt(ev.target.value), reload: true });
    }

    async azkSetPrefixes(ev) {
        const prefixes = ev.target.value
            .split(",")
            .map((prefix) => prefix.trim())
            .filter(Boolean);
        if (prefixes.join(", ") === this.azkPrefixes) {
            return;
        }
        // the server validates them (letters, digits, "." and "-")
        await this.filterClicked({ optionKey: "azk_tb.account_prefixes", optionValue: prefixes, reload: true });
    }
}

AccountReportController.registerCustomComponent(AzkTrialBalanceFilters);
