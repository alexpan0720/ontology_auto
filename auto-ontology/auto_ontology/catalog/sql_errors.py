# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Errors raised while parsing SQL against the catalog."""


class SqlParseError(Exception):
    """SQL could not be parsed or resolved against the catalog."""
