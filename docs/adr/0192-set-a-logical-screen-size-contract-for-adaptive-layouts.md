# Set a Logical Screen-Size Contract for Adaptive Layouts

RC MetaStudio will treat 1024 by 640 logical pixels as the Full-Usability Floor and will keep workflows operable at 800 by 600 logical pixels through Constrained Layout overflow. Layout policy and acceptance tests will use logical rather than physical pixels so the same contract applies across normal-density and high-DPI displays without resolution-specific hard-coded geometry.
