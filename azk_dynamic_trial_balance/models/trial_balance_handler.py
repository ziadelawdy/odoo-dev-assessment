from odoo import models


class AzkDynamicTrialBalanceReportHandler(models.AbstractModel):
    """Custom handler of the Dynamic Trial Balance.

    Inherits the native Trial Balance handler so the opening balance, the
    fiscal-year logic for P&L accounts, the Undistributed Profits/Losses line
    and the company scoping are the native ones by construction.
    """
    _name = 'azk.dynamic.trial.balance.report.handler'
    _inherit = ['account.trial.balance.report.handler']
    _description = 'Dynamic Trial Balance Custom Handler'
