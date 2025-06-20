# Nutriflap

This application stores its database and uploaded attachments in a directory
specified by `config.ini`.

Create a `config.ini` file based on the provided `config.ini.example` and set the
`data_dir` path to the folder where you want these files stored.

## Building a standalone executable

To package the application with PyInstaller use:

```bash
pyinstaller --noconfirm --onefile \
  --add-data "templates;templates" \
  --add-data "static;static" \
  --add-data "init_db.sql;." \
  --add-data "nutriflap.db;." app.py
```

The resulting executable will include the default database and, when run,
automatically open your browser to `http://127.0.0.1:5000/`.
