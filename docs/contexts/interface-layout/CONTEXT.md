# Interface Layout

This context defines the user-facing window roles that govern how RC MetaStudio adapts to available space and changing content.

## Language

**Window Archetype**:
A user-facing window role whose sizing behavior follows the kind of work performed in that window rather than one application-wide resizing rule.
_Avoid_: Window type, sizing mode

**Workspace Window**:
A primary work surface where users inspect or manipulate substantial content over time and may benefit from additional screen space. A Workspace Window may be modal or modeless; modality does not determine its sizing behavior.
_Avoid_: Main dialog, large window

**Workflow Window**:
A guided, multi-step surface whose content and required space may change as the user moves through the workflow.
_Avoid_: Wizard popup, step dialog

**Transactional Dialog**:
A focused surface for completing one short decision or data-entry action without becoming a continuing workspace.
_Avoid_: Small window, fixed dialog

**Transient Window**:
A short-lived status surface that communicates progress without asking the user to manage its size.
_Avoid_: Progress popup, temporary dialog

**Constrained Layout**:
A window state in which preferred content exceeds the usable screen space, so the window remains screen-bounded while its content can be reached through overflow navigation.
_Avoid_: Shrink-to-fit mode, clipped layout

**Geometry Ownership**:
The authority to change a visible window's outer size and position. Workspace and Workflow Windows transfer this authority to the user and window manager after initial display; Transactional Dialogs and Transient Windows retain application ownership.
_Avoid_: Resize mode, automatic sizing

**Full-Usability Floor**:
The smallest logical screen area at which every workflow must remain usable without operating-system-level clipping. RC MetaStudio's Full-Usability Floor is 1024 by 640 logical pixels.
_Avoid_: Minimum resolution, smallest supported monitor

**Logical Layout Space**:
The device-independent coordinate space in which RC MetaStudio defines window, control, spacing, and overflow behavior while Qt maps those measurements to the active display density.
_Avoid_: Scaled pixels, DPI-adjusted geometry

**Declarative Layout Contract**:
The canonical description of a window's content hierarchy, intrinsic sizing, expansion priorities, proportions, and overflow boundaries. Each window owns this contract rather than relying on inferred coordinates or application-wide descendant mutation.
_Avoid_: Geometry patch, runtime layout repair

**Remembered Workspace Placement**:
The last user-controlled size, position, and window state associated with a Workspace Window role, restored only when it remains reachable in the current screen configuration.
_Avoid_: Saved geometry, fixed startup size

**Adjustable Pane**:
One of two or more adjacent content regions whose relative share of a Workspace Window has independent user value and may therefore be directly resized and remembered.
_Avoid_: Layout column, resizable panel

**Intrinsic-Ratio Artifact**:
A visual result or diagram whose meaning and presentation require its horizontal and vertical dimensions to scale proportionally within an otherwise freely resizable viewport.
_Avoid_: Aspect-ratio window, fixed-shape panel

**Required Content**:
Text or controls that users must perceive or operate to understand, validate, or complete the current workflow. Required Content may reflow or move into overflow navigation but must not be elided or clipped.
_Avoid_: Important text, must-fit content

**Overflow Boundary**:
The form-owned boundary within which excess content becomes navigable without moving the window's primary actions offscreen. It is part of the Declarative Layout Contract rather than a runtime wrapper around arbitrary content.
_Avoid_: Scroll fix, automatic scroll area

**Semantic Size Invariant**:
A size relationship required by a control's meaning or valid interaction range rather than inherited from historical form geometry. Only such invariants may justify hard size constraints.
_Avoid_: Preferred pixel size, visual tweak

**Column-Width Ownership**:
The authority to change a user-adjustable table's displayed column widths. Workspace tables transfer this authority to the user after initial schema fitting; compact Transactional tables retain content-driven ownership.
_Avoid_: Resize mode, automatic columns

**Functional Icon**:
A non-branding visual symbol that identifies an application action, navigation direction, analysis, dataset type, or other interface function. The RC MetaStudio app icon, its source and packaging variants, and splash artwork are Brand Assets rather than Functional Icons.
_Avoid_: App artwork, branding icon

**Brand Asset**:
Artwork whose primary purpose is to identify RC MetaStudio as a product, including the app icon and splash screen. Brand Assets are governed separately from the Functional Icon system.
_Avoid_: Functional icon, toolbar icon

**Action Icon**:
A Functional Icon for a familiar application command or navigation direction, expressed as a compact professional symbol with clear geometry, strong contrast, and consistent optical weight.
_Avoid_: Decorative command illustration, toy-like glyph

**Integrated Action Cue**:
A compact plus, minus, arrow, pencil, or related operation mark incorporated into an Action Icon's primary geometry instead of appearing as an oversized floating badge.
_Avoid_: Sticker badge, bubble control, detached decorative mark

**Conventional Icon Metaphor**:
An established desktop or statistical symbol retained for immediate recognition, with modernization limited to geometry, color, scale, and rendering rather than novelty-driven replacement. Canonical action examples include a folder for Open, floppy disk for Save, clipboard for Paste, curved arrows for Undo and Redo, and a power symbol for Quit.
_Avoid_: Novel illustration, metaphor redesign, unfamiliar substitute

**Statistical Concept Icon**:
A Functional Icon for an analysis, data type, or statistical concept whose professional metaphor may use a restrained two- or three-color semantic palette to distinguish meaning at dense desktop-interface sizes.
_Avoid_: Analysis logo, decorative chart

**Portable Icon Set**:
The complete collection of self-contained Functional Icon assets checked into and bundled with RC MetaStudio so the same symbols are available on every supported operating system.
_Avoid_: System icon font, remotely loaded icon set

**Functional Icon Package**:
The semantic `images/icons` resource hierarchy that groups Functional Icon Masters into actions, analyses, and dataset types and exposes matching stable Qt resource paths.
_Avoid_: Function icon set, toolbar icons, miscellaneous images

**Functional Icon Master**:
The canonical SVG representation of a Functional Icon from which RC MetaStudio loads or derives every packaged rendering of that symbol.
_Avoid_: Source bitmap, generated preview

**Professional Scientific Icon**:
An RC MetaStudio Functional Icon optimized for a professional statistical desktop interface through restrained color, crisp contrast, compact geometry, and legibility at 16-to-24-pixel application surfaces.
_Avoid_: Cartoon icon, decorative illustration, consumer-app sticker

**Fluent-Inspired Icon**:
A Professional Scientific Icon that borrows Windows 11 clarity, spacing, geometric refinement, and semantic color while remaining subordinate to RC MetaStudio's restrained professional tone.
_Avoid_: Literal Fluent Color illustration, bright layered icon, Microsoft Fluent icon

**Theme-Neutral Icon**:
A transparent Functional Icon whose palette and contrast remain legible on light and dark neutral surfaces across Windows and macOS without separate platform- or theme-specific artwork; compact and standard size variants may still differ optically.
_Avoid_: Light icon, dark icon, Windows-only icon, macOS-only icon

**Icon Color Vocabulary**:
The stable semantic palette shared by Statistical Concept Icons: blue for primary analysis, teal for observations and measurement, violet for moderators and grouping, amber for ordered or iterative analysis, red for destructive or cautionary meaning, and neutral graphite for Action Icons and structure.
_Avoid_: Decorative palette, per-icon colors

**Icon Color Budget**:
The per-icon limit of one dominant color family, one optional same-family tonal layer, and one contrasting semantic accent only when that accent communicates an operation.
_Avoid_: Rainbow icon, unrelated accent colors, decorative multicolor layering

**Professional Color Treatment**:
The controlled semi-flat use of the Icon Color Vocabulary through consistent saturation, strong contrast, and restrained tonal layering, producing a modern scientific-desktop character that remains polished on Windows and macOS.
_Avoid_: Monochrome-only system, decorative rainbow palette, cartoon color treatment, platform-specific chrome imitation

**Analysis Icon Family**:
The transparent, high-contrast Statistical Concept Icons that retain a recognizable forest plot as their common anchor, using blue estimate squares, confidence-interval lines, and a reference line while grouping, ordering, omission, or a fitted trend distinguishes each analysis variant. Cumulative and leave-one-out share identical base geometry and differ through an integrated green plus or red minus; subgroup uses a restrained violet grouping bracket, and meta-regression uses a violet fitted trend.
_Avoid_: Pale supporting tiles, transparency haze, unrelated analysis illustrations, per-analysis metaphor

**Compact Analysis Icon**:
The simplified 18-pixel transparent member of an analysis icon pair, using fewer plot rows, optically stronger relative strokes, and high contrast for dense menus while preserving the family's metaphor and semantic cue.
_Avoid_: Shrunken standard icon, unrelated menu glyph

**Standard Analysis Icon**:
The 28-pixel transparent member of an analysis icon pair, using restrained additional plot detail while matching the compact member's geometry, color semantics, and professional visual language.
_Avoid_: Enlarged compact icon, decorative analysis illustration

**Dataset-Type Icon Family**:
The monochrome Statistical Concept Icons that use conventional path-rendered notation to distinguish one-arm and two-arm measures, with a 2-by-2 matrix for diagnostic data. A single platform-neutral slate ink preserves the approved notation geometry while remaining legible on both light and dark neutral surfaces.
_Avoid_: Unrelated dataset illustrations, decorative color, runtime font dependency

**Icon-Bearing Command**:
A reusable main-window command or selection control whose recognition and cross-surface consistency benefit from a Functional Icon. Routine dialog and workflow actions such as OK, Cancel, Back, and Next remain text-led unless their meaning cannot be communicated clearly by text alone.
_Avoid_: Every button, decorated dialog action

**Surface-Specific Icon Scale**:
The icon-size hierarchy that gives each UI surface an optically coherent symbol size: 28 pixels for the main toolbar, 18 pixels for analysis menus, 16 pixels for table decorations, 20 pixels for outcome navigation, and concept-specific larger slots in the dataset chooser.
_Avoid_: Universal icon size, scale every icon identically

**Optical Icon Footprint**:
The perceived mass, occupied area, and baseline alignment an icon presents within its assigned surface slot. Members of a family should appear equally prominent without forcing distinct silhouettes into identical raw bounds; naturally wide symbols may be slightly wider and naturally tall symbols slightly taller.
_Avoid_: Equal raw bounds with unequal perceived size, arbitrary legacy whitespace, mechanically uniform silhouette

**Optical Stroke Scale**:
The size-specific adjustment of stroke proportion and detail density so compact icons remain crisp and standard icons remain refined without mechanically scaling identical linework.
_Avoid_: Universal stroke width, mechanically scaled detail

**Compact Table Decoration**:
A subdued 16-pixel icon variant used repeatedly in table rows, simplified and reduced in chroma so it remains a secondary affordance rather than competing with the dataset.
_Avoid_: Repeated toolbar icon, full-color row ornament

**Icon-Language Pair**:
A specialized Functional Icon presented with an adjacent label, menu text, or accessible tooltip so its meaning is never carried by an unfamiliar statistical symbol alone. A conventional Action Icon may appear without visible text only when it retains an accessible name.
_Avoid_: Self-explanatory statistical icon, unlabeled symbol
