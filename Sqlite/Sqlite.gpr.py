register(IMPORT,
         id    = 'im_sqlite',
         name  = _('SQLite Import'),
         description =  _('SQLite is a common local database format'),
         version = '1.1.11',
         gramps_target_version = "6.0",
         status = STABLE,
         audience = EXPERT,
         fname = 'ImportSql.py',
         import_function = 'importData',
         extension = "sql"
)

register(EXPORT,
         id    = 'ex_sqlite',
         name  = _('SQLite Export'),
         description =  _('SQLite is a common local database format'),
         version = '1.1.11',
         gramps_target_version = "6.0",
         status = STABLE,
         audience = EXPERT,
         fname = 'ExportSql.py',
         export_function = 'exportData',
         extension = "sql",
         export_options = 'WriterOptionBox'
)
