"""Per-account reconciliation: native Odoo Trial Balance vs Dynamic Trial Balance.

Run inside an Odoo shell on a database where the module (and its demo) is installed:

    python odoo-bin shell -c <config> -d <database> --no-http < azk_dynamic_trial_balance/scripts/reconcile_tb.py

Prints a Markdown table (current fiscal year, current company) and rolls back.
"""
from odoo import fields  # noqa: F401  (available in the shell namespace anyway)


def _values(report, options):
    result = {}
    for line in report._get_lines(options):
        if report._get_markup(line.id) == 'parent_account':
            continue
        sections = {}
        for column in line.columns:
            if column.column_group_index is None:
                continue
            col_type = options['column_groups'][column.column_group_index]['forced_options']['trial_balance_column_type']
            value = column.no_format if isinstance(column.no_format, (int, float)) else 0.0
            sections.setdefault(col_type, {})[column.expression_label] = value

        def net(section):
            vals = sections.get(section, {})
            if 'balance' in vals and not ({'debit', 'credit'} <= vals.keys()):
                return vals['balance']
            return vals.get('debit', 0.0) - vals.get('credit', 0.0)

        result[line.name] = (net('initial_balance'), sections.get('period', {}).get('debit', 0.0),
                             sections.get('period', {}).get('credit', 0.0), net('end_balance'))
    return result


def main(env):
    company = env.company
    fiscal_year = company.compute_fiscalyear_dates(fields.Date.context_today(env['res.company']))
    date = {'date_from': fields.Date.to_string(fiscal_year['date_from']),
            'date_to': fields.Date.to_string(fiscal_year['date_to'])}
    tables = {}
    for xmlid in ('account_reports.trial_balance_report', 'azk_dynamic_trial_balance.dynamic_trial_balance_report'):
        report = env.ref(xmlid).with_context(allowed_company_ids=company.ids)
        options = report.get_options({'selected_variant_id': report.id, 'date': date, 'hierarchy': False})
        tables[xmlid] = _values(report, options)
    native, ours = tables.values()

    print(f"Company: {company.name} — period {date['date_from']} .. {date['date_to']}\n")
    print('| Account | Native Initial | Ours Initial | Native Debit | Ours Debit | Native Credit | Ours Credit | Native End | Ours End | Difference |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    worst = 0.0
    for name in native:
        n, o = native[name], ours.get(name, (0.0, 0.0, 0.0, 0.0))
        diff = max(abs(a - b) for a, b in zip(n, o))
        worst = max(worst, diff)
        print(f'| {name} | {n[0]:,.2f} | {o[0]:,.2f} | {n[1]:,.2f} | {o[1]:,.2f} | {n[2]:,.2f} | {o[2]:,.2f} | {n[3]:,.2f} | {o[3]:,.2f} | {diff:,.2f} |')
    missing = set(ours) - set(native)
    print(f'\nLines only in ours: {sorted(missing) or "none"} — largest difference: {worst:,.2f}')


main(env)  # noqa: F821  (``env`` is provided by odoo-bin shell)
env.cr.rollback()  # noqa: F821
