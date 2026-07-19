# Remove dynamic Qt properties from application state

Application logic will not use QObject dynamic properties as hidden state. Existing application-owned `setProperty()` and `property()` pairs will become typed Python attributes or explicit state objects with defined ownership and lifetime. Generated form code may set genuine Qt-declared widget properties required by Designer forms, but arbitrary `QVariant`-like property storage is excluded from handwritten code and from the typed application contract.
