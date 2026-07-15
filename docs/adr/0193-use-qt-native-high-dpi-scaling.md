# Use Qt-Native High-DPI Scaling

RC MetaStudio will enable Qt high-DPI scaling and high-DPI pixmaps before constructing the application, define layout behavior exclusively in Logical Layout Space, and avoid custom application-wide DPI multipliers. Images used in layout calculations must honor their device-pixel ratio, and windows will reevaluate screen bounds when screen assignment or effective DPI changes so Qt remains the single scaling authority across supported platforms.
