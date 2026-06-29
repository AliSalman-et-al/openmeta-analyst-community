# Use Standard Binary Analysis as the First GUI Slice

After the headless analysis regression harness is in place, the first user-visible GUI compatibility slice will be the standard binary analysis workflow: open an existing `.oma` sample dataset, display the data table, run a binary random-effects meta-analysis, and show the result summary plus forest plot. This path exercises file loading, core data models, the main window, table display, R invocation, result rendering, and generated plot display without requiring every dialog and analysis mode to be ported at once.

Other GUI workflows should be brought forward after this slice is runnable and comparable against the reference implementation.
