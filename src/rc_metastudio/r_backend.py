from typing import NoReturn


class AnalysisBackendUnavailableError(RuntimeError):
    """Raised when the configured R analysis backend cannot service requests."""


_REAL_BACKEND = None


def is_backend_installed() -> bool:
    """Return whether startup composed the real or explicitly injected bridge."""
    return _REAL_BACKEND is not None


def _analysis_unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AnalysisBackendUnavailableError(
        "The analysis backend (in-process rpy2/R) is not available in this "
        "build, so meta-analyses cannot be run."
    )


def install_r_backend():
    """Configure and return the one real in-process embedded-R backend."""
    global _REAL_BACKEND
    if _REAL_BACKEND is not None:
        return _REAL_BACKEND
    try:
        from rc_metastudio import r_runtime

        r_runtime.configure_bundled_r_environment()
        from rc_metastudio import r_bridge

        _REAL_BACKEND = r_bridge
        return _REAL_BACKEND
    except Exception as error:
        raise AnalysisBackendUnavailableError(
            "Unable to start the embedded R runtime. Install the pinned R/RCMetaR "
            "runtime or repair the packaged integration kit, then restart RC MetaStudio."
        ) from error
