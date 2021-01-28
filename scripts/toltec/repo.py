# Copyright (c) 2021 The Toltec Contributors
# SPDX-License-Identifier: MIT
"""
Build the package repository.
"""

from datetime import datetime
import gzip
import logging
import os
import textwrap
from typing import Dict, List, Optional
import requests
from .recipe import GenericRecipe, Package
from .util import file_sha256, HTTP_DATE_FORMAT

PackageListByRecipe = Dict[str, Dict[str, List[str]]]
logger = logging.getLogger(__name__)


class Repo:
    """Repository of Toltec packages."""

    def __init__(self, recipe_dir: str, repo_dir: str) -> None:
        """
        Initialize a package repository.

        :param recipe_dir: directory where recipe definitions are stored
        :param repo_dir: directory where built packages are stored
        """
        self.recipe_dir = recipe_dir
        self.repo_dir = repo_dir
        self.generic_recipes = {}

        for name in os.listdir(self.recipe_dir):
            if name[0] != ".":
                self.generic_recipes[name] = GenericRecipe.from_file(
                    os.path.join(self.recipe_dir, name)
                )

    def fetch_packages(
        self, remote: Optional[str], fetch_missing: bool
    ) -> PackageListByRecipe:
        """
        Fetch missing packages.

        :param remote: remote server from which to check for existing packages
        :param fetch_missing: pass true to fetch missing packages from remote
        :returns: missing packages grouped by parent recipe and architecture
        """
        logger.info("Scanning for missing packages")
        missing: PackageListByRecipe = {}

        for name, generic_recipe in self.generic_recipes.items():
            missing_for_generic: Dict[str, List[str]] = {}

            for arch, recipe in generic_recipe.recipes.items():
                missing_for_recipe: List[str] = []

                for package in recipe.packages.values():
                    if not self.fetch_package(package, remote, fetch_missing):
                        logger.info(
                            "Package %s (%s) is missing",
                            package.pkgid(),
                            recipe.name,
                        )
                        missing_for_recipe.append(package.name)

                if missing_for_recipe:
                    missing_for_generic[arch] = missing_for_recipe

            if missing_for_generic:
                missing[name] = missing_for_generic

        return missing

    def fetch_package(
        self, package: Package, remote: Optional[str], fetch_missing: bool
    ) -> bool:
        """
        Fetch a package.

        :param package: package to fetch
        :param remote: remote server from which to check for existing packages
        :param fetch_missing: pass true to fetch missing packages from remote
        :returns: true if the package already exists or was fetched
            successfully, false if it needs to be built from source
        """
        filename = package.filename()
        local_path = os.path.join(self.repo_dir, filename)

        if os.path.isfile(local_path):
            return True

        if remote is None:
            return False

        remote_path = os.path.join(remote, filename)

        if not fetch_missing:
            return requests.head(remote_path).status_code == 200

        req = requests.get(remote_path)

        if req.status_code != 200:
            return False

        with open(local_path, "wb") as local:
            for chunk in req.iter_content(chunk_size=1024):
                local.write(chunk)

        last_modified = int(
            datetime.strptime(
                req.headers["Last-Modified"],
                HTTP_DATE_FORMAT,
            ).timestamp()
        )

        os.utime(local_path, (last_modified, last_modified))
        return True

    def make_index(self) -> None:
        """Generate index files for all the packages in the repo."""
        logger.info("Generating package index")
        index_path = os.path.join(self.repo_dir, "Packages")
        index_gzip_path = os.path.join(self.repo_dir, "Packages.gz")

        with open(index_path, "w") as index_file:
            with gzip.open(index_gzip_path, "wt") as index_gzip_file:
                for generic_recipe in self.generic_recipes.values():
                    for recipe in generic_recipe.recipes.values():
                        for package in recipe.packages.values():
                            filename = package.filename()
                            local_path = os.path.join(self.repo_dir, filename)

                            if not os.path.isfile(local_path):
                                continue

                            control = package.control_fields()
                            control += textwrap.dedent(
                                f"""\
                                Filename: {filename}
                                SHA256sum: {file_sha256(local_path)}
                                Size: {os.path.getsize(local_path)}

                                """
                            )

                            index_file.write(control)
                            index_gzip_file.write(control)
