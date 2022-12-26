from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    env.cr.execute("""UPDATE l10n_uy_adenda SET apply_on = 'account.move'""")
