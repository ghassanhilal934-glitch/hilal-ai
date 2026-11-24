# -*- coding: utf-8 -*-
"""توافق pydantic v1 مع Python 3.13 في Termux (يُحمّل تلقائياً)"""
import sys
import typing

if sys.version_info >= (3, 13) and hasattr(typing.ForwardRef, "_evaluate"):
    _original = typing.ForwardRef._evaluate

    def _patched(self, globalns, localns, *args, **kwargs):
        return _original(
            self,
            globalns,
            localns,
            args[0] if args else None,
            recursive_guard=kwargs.get("recursive_guard", set()),
        )

    typing.ForwardRef._evaluate = _patched
