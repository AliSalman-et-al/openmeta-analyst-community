# Use Qt6 native fractional scaling

RC MetaStudio will retain Qt6's default `PassThrough` fractional scale-factor policy rather than restore Qt5-style integer rounding. Native packaged qualification will cover 125%, 150%, and 175% scaling, and application geometry or rendering defects exposed there will be fixed at their owning boundary. A different rounding policy may be introduced only for a demonstrated unavoidable platform defect through an explicit documented exception.
