# Use only explicit signal connections

RC MetaStudio will wire application behavior only through explicit bound-signal `.connect()` calls in handwritten code. Build-generated form modules will not use object-name-based `QMetaObject.connectSlotsByName()` auto-connection; overloaded built-in signals will select the intended overload explicitly. This keeps connection ownership reviewable and prevents widget renames, duplicate auto-connections, or changed default overloads from silently altering behavior.
