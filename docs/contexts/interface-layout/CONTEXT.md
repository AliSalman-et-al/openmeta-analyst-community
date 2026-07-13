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
