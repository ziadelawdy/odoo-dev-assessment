import { registry } from "@web/core/registry";

const summaryHas = (text) => ({
    content: `filter summary shows "${text}"`,
    trigger: `#warnings .alert:contains("${text}")`,
});

registry.category("web_tour.tours").add("azk_tb_filter_bar", {
    steps: () => [
        { content: "report loaded", trigger: '.line_name:contains("Tour Parent")' },
        { content: "custom filter bar", trigger: ".azk-tb-filters" },
        { content: "PDF button", trigger: "button:contains('PDF')" },
        { content: "XLSX button", trigger: "button:contains('XLSX')" },
        { content: "unposted switch", trigger: ".azk-tb-toggle-all_entries input" },
        { content: "hierarchy switch", trigger: ".azk-tb-toggle-hierarchy input" },
        // Skip zero balance
        { content: "toggle skip zero", trigger: ".azk-tb-toggle-skip_zero_balance input", run: "click" },
        summaryHas("Zero balances skipped"),
        { content: "skip zero is on", trigger: ".azk-tb-toggle-skip_zero_balance input:checked" },
        // Amount currency
        { content: "toggle amount currency", trigger: ".azk-tb-toggle-show_amount_currency input", run: "click" },
        summaryHas("Amount in currency shown"),
        // Account prefixes
        { content: "type a prefix", trigger: "input.azk-tb-prefixes", run: "edit 15" },
        { content: "apply prefixes", trigger: "input.azk-tb-prefixes", run: "press Enter" },
        summaryHas("Account prefixes: 15"),
        // Only parents + level
        { content: "no level selector yet", trigger: "body:not(:has(select.azk-tb-level))" },
        { content: "toggle only parents", trigger: ".azk-tb-toggle-only_parents input", run: "click" },
        { content: "level selector shown", trigger: "select.azk-tb-level", run: "select 2" },
        summaryHas("Hierarchy up to level 2"),
        { content: "hierarchy switched on with only parents", trigger: ".azk-tb-toggle-hierarchy input:checked" },
    ],
});
