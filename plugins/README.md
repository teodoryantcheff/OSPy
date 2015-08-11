OSPy Plug-ins
====

Currently all plug-ins are in this repository.
In the near future, the plug-ins will be separated from the main repository to provide easier plug-in installation.
To support this, plug-ins have been standardized and put in individual folders.
A plug-in is only allowed to install/store files in its own folder.

The basic structure is as follows:

    plugins
    + plugin_name
      + data
      + docs
      + static
      + templates
      + i18n (future)
      + __init__.py
      \ README.md

The static files will be made accessible automatically at the following location:
/plugins/plugin_name/static/...

All *.md files in the docs directory will be visible in the help page.
The README.md (if available) will be the first entry in the help page
and might be used in the future as a description for plug-in browsing.