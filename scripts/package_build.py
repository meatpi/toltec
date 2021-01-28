#!/usr/bin/env python3
# Copyright (c) 2021 The Toltec Contributors
# SPDX-License-Identifier: MIT
"""Build packages from a given recipe."""

import argparse
import logging
import os
import sys
from toltec import paths
from toltec.builder import Builder
from toltec.util import argparse_add_verbose, LOGGING_FORMAT
from toltec.recipe import GenericRecipe

parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument(
    "recipe_name",
    metavar="RECIPENAME",
    help="name of the recipe to build",
)

parser.add_argument(
    "-a",
    "--arch-name",
    metavar="ARCHNAME",
    action="append",
    help="""only build for the given architecture (can
    be repeated)""",
)

parser.add_argument(
    "packages_names",
    nargs="*",
    metavar="PACKAGENAME",
    help="list of packages to build (default: all packages from the recipe)",
)

argparse_add_verbose(parser)

args = parser.parse_args()
logging.basicConfig(format=LOGGING_FORMAT, level=args.verbose)
builder = Builder(paths.WORK_DIR, paths.REPO_DIR)

recipe = GenericRecipe.from_file(
    os.path.join(paths.RECIPE_DIR, args.recipe_name)
)
arch_packages_names = None  # pylint:disable=invalid-name

if args.arch_name or args.packages_names:
    arch_packages_names = dict(
        (arch or "", args.packages_names if args.packages_names else None)
        for arch in args.arch_name or recipe.archs
        if arch in recipe.archs
    )

if not builder.make(recipe, arch_packages_names):
    sys.exit(1)
