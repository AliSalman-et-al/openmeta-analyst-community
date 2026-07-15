# Replace pickle RCMS storage during the Qt6 cutover

The Qt6 hard cutover will replace pickle-based `.rcms` storage with the Versioned Project Format and remove pickle loading and historical SIP/Qt-value decoding from the application runtime. Because no pickle-era RC MetaStudio release has reached users, no legacy converter will be shipped or retained. Every committed `.rcms` sample project will instead be exported to the new format before the legacy serializer is deleted and verified against its pre-conversion project semantics.
