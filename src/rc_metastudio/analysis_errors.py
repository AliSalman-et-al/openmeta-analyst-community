# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Domain errors raised while executing analyses."""


class DiagnosticExecutionError(RuntimeError):
    """A diagnostic R execution failed and may be retried per metric."""
