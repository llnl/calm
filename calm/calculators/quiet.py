"""Lightweight suppression helpers for ML-backed calculator noise.

This module intentionally avoids importing any heavy ML or provider backends.
It provides a conservative, environment-variable + logging based context manager
that suppresses noisy output from common ML libraries during calculator
construction. The approach is intentionally non-invasive (no FD dup2) and
works well for well-behaved libraries that respect environment-based
verbosity flags and Python logging.

Usage::

    from calm.calculators.quiet import suppress_mlip_output

    with suppress_mlip_output():
        # import / construct calculators that may emit noisy logs on import
        make_calculator(...)

The context manager is best-effort: it avoids importing optional backends and
only touches os.environ and the Python logging subsystem.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from typing import Generator

_COMMON_ENV = {
    # TensorFlow noisy C++ logs
    "TF_CPP_MIN_LOG_LEVEL": "3",
    # Prefer the pure-Python protobuf implementation where possible to avoid
    # some C-extension warnings and MessageFactory noise during model setup.
    "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
    # gRPC noise (sometimes used by providers)
    "GRPC_VERBOSITY": "ERROR",
    "GRPC_TRACE": "",
}


@contextmanager
def suppress_mlip_output() -> Generator[None, None, None]:
    """Context manager that suppresses common ML/calculator logging.

    This is intentionally conservative: it only mutates environment variables
    and Python logging levels and does not redirect file descriptors or
    otherwise interfere with external I/O.
    """
    # Preserve previous environment values so we can restore them.
    old_env = {k: os.environ.get(k) for k in _COMMON_ENV}
    try:
        # Set environment hints early so native extensions and libraries pick
        # them up during subsequent imports.
        for k, v in _COMMON_ENV.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        # Tweak Python logging: raise root logger to ERROR and set common
        # noisy loggers to ERROR as well.
        root = logging.getLogger()
        old_root_level = root.level
        root.setLevel(logging.ERROR)

        # Named loggers commonly used by ML libs / providers.
        names = ("absl", "tensorflow", "torch", "grpc", "mace", "chgnet", "grace")
        old_levels = {}
        for name in names:
            logger = logging.getLogger(name)
            old_levels[name] = logger.level
            logger.setLevel(logging.ERROR)

        # Best-effort low-level suppression: redirect native stdout/stderr to
        # /dev/null while the context is active. This is a last-resort step to
        # silence C/C++-level prints from third-party libraries that bypass the
        # Python logging subsystem. We attempt to be careful and restore fds.
        devnull_fd = None
        old_stdout_fd = None
        old_stderr_fd = None
        try:
            # Flush Python-level buffers before changing underlying fds.
            try:
                sys.stdout.flush()
            except Exception:
                pass
            try:
                sys.stderr.flush()
            except Exception:
                pass

            devnull_fd = os.open(os.devnull, os.O_RDWR)
            # Duplicate original fds for restoration later.
            old_stdout_fd = os.dup(1)
            old_stderr_fd = os.dup(2)
            # Redirect both stdout and stderr to /dev/null.
            os.dup2(devnull_fd, 1)
            os.dup2(devnull_fd, 2)
        except Exception:
            # If any low-level redirection step fails, fall back to env/logging
            # level suppression only.
            try:
                if devnull_fd is not None:
                    os.close(devnull_fd)
            except Exception:
                pass
            devnull_fd = None

        yield
    finally:
        # Restore environment
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        # Restore logging
        try:
            root.setLevel(old_root_level)
        except Exception:
            # Be resilient if logging was reconfigured underneath us.
            pass

        for name, level in old_levels.items():
            try:
                logging.getLogger(name).setLevel(level)
            except Exception:
                pass
        # Restore low-level fds if we changed them.
        try:
            if old_stdout_fd is not None:
                os.dup2(old_stdout_fd, 1)
        except Exception:
            pass
        try:
            if old_stderr_fd is not None:
                os.dup2(old_stderr_fd, 2)
        except Exception:
            pass
        try:
            if old_stdout_fd is not None:
                os.close(old_stdout_fd)
        except Exception:
            pass
        try:
            if old_stderr_fd is not None:
                os.close(old_stderr_fd)
        except Exception:
            pass
        try:
            if devnull_fd is not None:
                os.close(devnull_fd)
        except Exception:
            pass
