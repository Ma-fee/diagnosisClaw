#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from contextlib import suppress

from .tqdm import TqdmStream


def setup_logger():
    """
    Setup the logger with a TqdmStream handler and a colored formatter.
    """
    try:
        from rich.logging import RichHandler

        stream = RichHandler(rich_tracebacks=True, markup=True)
    except ImportError:
        stream = TqdmStream()
        with suppress(ImportError):
            from colorlog import ColoredFormatter

            stream.setFormatter(
                ColoredFormatter(
                    """[%(log_color)s%(levelname)s%(reset)s][%(blue)s%(asctime)s%(reset)s]"""
                    """[%(red)s%(name)s:%(funcName)s@%(lineno)d%(reset)s] %(message)s"""
                )
            )
    fmt = "[%(levelname)s][%(asctime)s][%(name)s:%(funcName)s@%(lineno)d] %(message)s"

    try:
        logging.basicConfig(format=fmt, level=logging.INFO, handlers=stream, force=True)
    except ValueError:
        logging.basicConfig(format=fmt, level=logging.INFO, handlers=stream)
