# Inherit Platform Fonts for Adaptive Layouts

Normal RC MetaStudio forms will inherit the platform or application font rather than hard-code Verdana, Courier, or absolute point sizes. Visual hierarchy will use semantic weight and style, monospaced Results content will use Qt's system fixed-width font, and the layout acceptance matrix will include enlarged application fonts so size hints, wrapping, controls, and overflow remain valid under user font scaling.
