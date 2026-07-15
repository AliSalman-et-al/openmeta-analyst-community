# QtSvg and svglite style interoperability

## Question

What is the most robust way to prevent study confidence intervals from disappearing when RC MetaStudio displays an `svglite` forest plot through PyQt5/QtSvg?

## Finding

Treat the problem as an SVG compatibility-normalization problem at the display-artifact boundary, not as a RevMan-specific drawing bug.

`svglite` deliberately puts its common shape defaults in an embedded descendant CSS rule. Its source emits one rule for `.svglite line`, `polyline`, `polygon`, `path`, `rect`, and `circle`, setting `fill`, `stroke`, line caps, joins, and miter limit. The device then deliberately omits an element's `stroke` when the requested color is black because black is supplied by that rule. It similarly omits default round caps and joins. There is no public `svglite()` option to request fully inline styles; its documented arguments configure dimensions, background, fonts, identifiers, text sizing, scaling, and file validity, but not CSS emission. [svglite default stylesheet](https://github.com/r-lib/svglite/blob/518c837c1283ad5752c2d595a0a84d2e169111ab/src/devSVG.cpp#L648-L679), [svglite black-stroke optimization](https://github.com/r-lib/svglite/blob/518c837c1283ad5752c2d595a0a84d2e169111ab/src/devSVG.cpp#L382-L391), [svglite device API](https://github.com/r-lib/svglite/blob/518c837c1283ad5752c2d595a0a84d2e169111ab/R/SVG.R#L84-L128)

Qt documents its software SVG renderer as supporting SVG 1.2 Tiny as a baseline plus selected extensions. It explicitly warns that unsupported features are ignored where possible and that SVGs depending on them may have omissions or errors. Consequently, validity (`QSvgRenderer.isValid()`) is not evidence of faithful rendering. [Qt vector image format support](https://doc.qt.io/qt-6/topics-vectorimageformats.html)

Qt 5.15 source does contain a CSS parser and selector adapter for SVG, including parent traversal and class lookup. It also parses per-element inline `style` declarations into SVG attributes. That makes the observed failure a QtSvg interoperability defect or limitation in this particular document/render path, rather than evidence that SVG descendant CSS is invalid. [Qt 5.15 SVG CSS selector adapter](https://github.com/qt/qtsvg/blob/62c4a8da3114174ea5b2c4ea46d2ab848066d534/src/svg/qsvghandler.cpp#L443-L558), [Qt 5.15 inline-style parsing](https://github.com/qt/qtsvg/blob/62c4a8da3114174ea5b2c4ea46d2ab848066d534/src/svg/qsvghandler.cpp#L227-L329)

The SVG 1.1 specification permits both embedded CSS and element-level presentation attributes. It calls presentation attributes broadly supported and especially suitable for tool interoperability; conforming viewers must support them. Inline `style` has higher cascade specificity than selector rules. [SVG 1.1 styling and presentation attributes](https://www.w3.org/TR/SVG11/styling.html#UsingPresentationAttributes), [CSS Style Attributes cascade](https://www.w3.org/TR/css-style-attr/#cascading)

## Options considered

### 1. Configure svglite to emit inline defaults

Best in principle, but unavailable through the supported API. Using a near-black color merely defeats one current optimization, changes requested output, and leaves other stylesheet defaults (`fill`, caps, joins, and miter limit) dependent on QtSvg. Forking or patching the bundled R package would add an avoidable maintenance burden.

### 2. Normalize generated SVG with an XML-aware compatibility pass

Recommended. After `dev.off()`, parse the SVG as XML and materialize the known svglite default declarations on every applicable element inside the `.svglite` group. Preserve explicit element declarations and their cascade precedence. At minimum normalize `fill`, `stroke`, `stroke-linecap`, `stroke-linejoin`, and `stroke-miterlimit` for `line`, `polyline`, `polygon`, `path`, `rect`, and `circle`; handle the glyph-group exception so glyph paths remain `fill: inherit; stroke: none`. Keep the original embedded stylesheet if desired for standards-compliant consumers.

This is more robust than a regular-expression pass that only adds black `stroke` to `line` and `polyline`: that narrower pass encodes the current symptom, does not cover all shapes governed by the same rule, does not carry the other omitted defaults, and can become fragile around quoting, attribute order, namespaces, or multiline tags. An XML transform makes the contract explicit and testable while retaining vector quality and the current Qt/PyQt architecture.

Prefer presentation attributes (`stroke="#000000"`, etc.) for defaults because the SVG specification identifies them as the broad-interoperability representation. Preserve any existing inline style/property by not overwriting it. If exact CSS cascade flattening beyond svglite's stable built-in rules is ever required, use a real CSS parser rather than growing selector logic in application code.

### 3. Normalize only in Python before constructing `QSvgRenderer`

Viable but weaker as the primary seam. Loading normalized bytes into `QSvgRenderer` protects the Results window while leaving saved display artifacts incompatible with other constrained SVG consumers and duplicates SVG knowledge on the GUI side. It is useful as defense in depth for externally supplied SVG, not necessary for managed artifacts generated by RCMetaR.

### 4. Rasterize through librsvg for display

Reliable fallback because RC MetaStudio already uses `rsvg` for raster/PDF exports, and the reported direct raster render preserved the intervals. However, a fixed bitmap sacrifices resolution-independent zoom, consumes more memory at publication-sized dimensions, and requires DPR/viewport-aware rerendering to avoid blur. Use only if normalization fails validation or QtSvg rejects the artifact.

### 5. Replace QtSvg or the SVG device

Qt WebEngine would bring a browser-grade CSS/SVG engine but is a large runtime and packaging expansion for a results pane. Moving to Qt 6 may improve SVG coverage, but Qt still documents subset behavior and the repository deliberately targets PyQt5, so it is not a focused fix. Base R's Cairo SVG device produces substantially different, larger artifacts and often converts text to paths; changing devices risks typography/layout drift and still requires consumer verification. None offers a lower-risk fix than normalizing svglite's small, known stylesheet contract.

## Recommendation

Implement one shared, XML-aware `svglite` compatibility normalizer in the RCMetaR plot-device layer and run it for every managed SVG display artifact, regardless of plot style or plot type. Do not key it to RevMan or to black CI lines. This fixes the underlying class: any property that svglite intentionally inherits from its built-in stylesheet becomes explicit before QtSvg sees it.

Verification should cover:

1. structural tests for all six governed SVG shape types, explicit-color preservation, glyph-group exceptions, both `.svg` and compressed `.svgz`, and idempotence;
2. a real PyQt5 `QSvgRenderer` pixel test proving a default-black line appears (artifact-size tests and `isValid()` are insufficient);
3. representative Default, RevMan, and BMJ rendered plots to detect visual drift;
4. a raster fallback only when vector validation fails, with its use surfaced diagnostically rather than silently becoming the normal path.

## Decision summary

| Approach | Robustness | Vector fidelity | Scope/risk | Verdict |
|---|---:|---:|---:|---|
| Change color to near-black | Low | High | Low | Reject |
| Regex-add stroke to CI lines | Medium-low | High | Low | Replace with general normalizer |
| XML-aware svglite default flattening | High | High | Moderate | Recommend |
| Python display-only normalization | Medium-high | High | Moderate | Optional defense in depth |
| librsvg raster display | High rendering compatibility | Low | Moderate | Fallback |
| QtWebEngine/Qt 6/other device | Variable | High | High | Defer |
