# Treat Qt UI Files as Canonical Resources

RC MetaStudio should treat Qt Designer `.ui` files as the canonical source for GUI form definitions under the packaged application resources. Generated Python UI modules may be kept only as transitional compatibility during the mechanical layout migration or produced during build, test, and packaging; they should not remain hand-maintained source modules long term.

This reduces generated-code churn during the RC MetaStudio rename and keeps GUI layout changes anchored to the Qt resource source of truth.

