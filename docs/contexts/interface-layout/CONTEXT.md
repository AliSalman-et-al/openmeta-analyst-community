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
A Functional Icon for a familiar application command or navigation direction, expressed as a compact filled symbol with clear geometry and restrained Fluent Color layering.
_Avoid_: Outline-only glyph, monochrome system font

**Statistical Concept Icon**:
A Functional Icon for an analysis, data type, or statistical concept whose metaphor may use a restrained two- or three-color palette to distinguish meaning.
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

**Fluent-Inspired Icon**:
An original RC MetaStudio Functional Icon that follows Windows 11 color-icon principles such as filled geometric shapes, soft corners, bright layered color, restrained gradients, minimal detail, and a strong small-size silhouette without copying or redistributing Microsoft glyph artwork.
_Avoid_: Microsoft Fluent icon, Segoe glyph

**Theme-Neutral Icon**:
A Functional Icon whose transparent SVG and restrained palette remain legible on both light and dark neutral interface backgrounds without a separate theme-specific asset.
_Avoid_: Light icon, dark icon

**Icon Color Vocabulary**:
The stable semantic palette shared by Statistical Concept Icons: blue for primary analysis, teal for observations and measurement, violet for moderators and grouping, amber for ordered or iterative analysis, red for destructive or cautionary meaning, and neutral graphite for Action Icons and structure.
_Avoid_: Decorative palette, per-icon colors

**Analysis Icon Family**:
The Statistical Concept Icons that retain a recognizable forest plot as their common anchor, using estimate squares, confidence-interval lines, and a reference line while grouping, ordering, omission, or a fitted trend distinguishes each analysis variant.
_Avoid_: Unrelated analysis illustrations, per-analysis metaphor

**Dataset-Type Icon Family**:
The monochrome Statistical Concept Icons that use conventional path-rendered notation to distinguish one-arm and two-arm measures, with a 2-by-2 matrix for diagnostic data.
_Avoid_: Unrelated dataset illustrations, decorative color, runtime font dependency

**Icon-Bearing Command**:
A reusable main-window command or selection control whose recognition and cross-surface consistency benefit from a Functional Icon. Routine dialog and workflow actions such as OK, Cancel, Back, and Next remain text-led unless their meaning cannot be communicated clearly by text alone.
_Avoid_: Every button, decorated dialog action

**Icon-Language Pair**:
A specialized Functional Icon presented with an adjacent label, menu text, or accessible tooltip so its meaning is never carried by an unfamiliar statistical symbol alone. A conventional Action Icon may appear without visible text only when it retains an accessible name.
_Avoid_: Self-explanatory statistical icon, unlabeled symbol
