"""Standardised setup.py for templated python package projects.

This setup.py is intended only to be used with the included build scripts.

To use this file, you should only need to update the values in the constants
section. Everything should then be handled for you.

The configuration constants are arranged into 3 sections:
- Basic Configuration:
    The most commonly used setup arguments.

- Intermediate Configuration:
    Less commonly used setup arguments. In a different section to avoid clutter.

- Advanced Configuration:
    Arguments that could break everything because of assumptions built into the
    template.

References:
    - https://packaging.python.org/specifications/core-metadata/
    - https://docs.python.org/3/distutils/setupscript.html#additional-meta-data
    - https://setuptools.readthedocs.io/en/latest/setuptools.html#new-and-changed-setup-keywords
    - https://github.com/pypa/sampleproject
"""
### IMPORTS
### ============================================================================
## Standard Library
import os.path
from typing import Optional, Tuple

## Third Party
from setuptools import setup, find_packages

## Local

### CONSTANTS
### ============================================================================
## Basic Configuration
## -----------------------------------------------------------------------------
# Your package name should be in `kebab-case` and will be the name used when
# using pip to install the package. e.g. `pip install kebab-case`.
#
# This name will transformed into `snake_case` which is what you will use to
# to import your package. e.g. `import snake_case`.
#
# See also:
#   - https://packaging.python.org/specifications/core-metadata/#name
PACKAGE_NAME = "nserver"

# To enable reuse, we use calculate the python package name now.
# DO NOT EDIT THIS UNLESS ADVANCED USER.
# Changing this value may break this repository.
PACKAGE_PYTHON_NAME = PACKAGE_NAME.replace("-", "_")

# Your version should follow semantic versioning.
# Suggested formats are:
#   - `MAJOR.MINOR.PATCH` e.g. 3.6.8
#   - `YYYY.MM.RELAESE` e.g. 2019.6.14
#   - `YY.MM.RELEASE` e.g. 19.6.1
#
# Note: This value will be used by build scripts to populated <your_package>._version
#
# See also:
#   - https://www.python.org/dev/peps/pep-0440/
PACKAGE_VERSION = "0.1.0"

PACKAGE_DESCRIPTION = "DNS Name Server Framework"

PACKAGE_URL = "https://github.com/nhairs/nserver"

PACKAGE_AUTHOR = "Nicholas Hairs"

PACKAGE_AUTHOR_EMAIL = "info+nserver@nicholashairs.com"

PACKAGE_DEPENDENCIES = [
    "dnslib",
    "tldextract",
]


## Intermediate Configuration
## -----------------------------------------------------------------------------
# Entry Points
# See also:
#   - https://setuptools.readthedocs.io/en/latest/setuptools.html#automatic-script-creation
PACKAGE_ENTRY_POINTS = None

# Extra dependencies
# See also:
#   - https://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies
PACKAGE_EXTRA_DEPENDENCIES = {}

# Include package data.
# See also:
#   - https://setuptools.readthedocs.io/en/latest/setuptools.html#including-data-files
INCLUDE_PACKAGE_DATA = {
    PACKAGE_NAME: ["py.typed"],
}

PACKAGE_DATA_FILES = None

EXCLUDE_PACKAGE_DATA = None

# Set the classifiers for this project. This is important if you are uploading
# to a package repository like PyPI
#   - https://pypi.org/classifiers/
PACKAGE_CLASSIFIERS = [
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    # Consider adding 3.8, 3.9 as they become available and are tested.
    "Development Status :: 3 - Alpha",  # Default to Alpha.
    "License :: OSI Approved :: MIT License",
    "Topic :: Internet",
    "Topic :: Internet :: Name Service (DNS)",
]

# Comma seperated list of keywords describing the package that can be used by
# the package repository to help users search for the package.
PACKAGE_KEYWORDS = None  # type: Optional[List[str]]

# Set the package maintainer for when the package is being maintained by someone
# other than the original author.
# See also:
#   - https://packaging.python.org/specifications/core-metadata/#maintainer
PACKAGE_MAINTAINER = None
PACKAGE_MAINTAINER_EMAIL = None

# Extra URLs that will be displayed on PyPI. Dict keys are what will be displayed
# on PyPI. Example:
#   PACKAGE_PROJECT_URLS = {
#       "Documentation": "https://twistedmatrix.com/documents/current/"
#       "Source": "https://github.com/twisted/twisted",
#       "Issues": "https://twistedmatrix.com/trac/report",
#   }
#
# Note: PACKAGE_URL will already be included.
# See also:
#   - https://packaging.python.org/guides/distributing-packages-using-setuptools/#project-urls
PACKAGE_PROJECT_URLS = None


# Set the licence which this project is released under.
# See also:
#   - https://packaging.python.org/specifications/core-metadata/#license
#
# DISCLAIMER:
#   THE FOLLOWING INFORMATION DOES NOT CONSTITUTE LEGAL ADVICE, IS NOT A
#   SUBSTITUTE FOR LEGAL ADVICE, AND SHOULD NOT BE RELIED ON AS SUCH.
#
# If you do no understand licencing this link provides a good starting point:
#   - https://opensource.guide/legal/
#
# The following link provides an overview of open source licences:
#   - https://choosealicense.com/appendix/
#
# If you intend to make your project open source then you should include a
# licence, if you don't it makes it difficult for others - particularly
# companies and other organisations to use your work.
# See also:
#   - https://choosealicense.com/no-permission/
#
# If you work for a company and intend to make this project available to others
# you should contact yout internal legal team for advice before doing so.
# See also:
#   - https://opensource.guide/legal/#what-does-my-companys-legal-team-need-to-know
PACKAGE_LICENCE = None


## Advanced Configuration
## -----------------------------------------------------------------------------
# Set the supported python versions. This allows you to raise the minimum
# supported version of python. This may be desirable if you are using backwards
# incompatible features from a newer version of python.
#
# Note: This package template has been designed only for the versions below and
# is unlikely to work older versions of python (e.g. 2.7)
PYTHON_VERSIONS = ">=3.6, <4"

# Developer notes: If you increase the minimum version you should also change:
#   - black target
#   - something about docker containers when testing or some shit.

# Set whether this package is zip safe. The below code can be replaced in order
# to manually set this constant.
# See also:
#   - https://setuptools.readthedocs.io/en/latest/setuptools.html#setting-the-zip-safe-flag
if INCLUDE_PACKAGE_DATA or PACKAGE_DATA_FILES:
    ZIP_SAFE = False
else:
    ZIP_SAFE = None

# Change the behaviour of `setuptools.find_packages`.
# See also:
#   - https://setuptools.readthedocs.io/en/latest/setuptools.html#using-find-packages
FIND_PACKAGES_EXCLUDE = []
FIND_PACKAGES_INCLUDE = [PACKAGE_PYTHON_NAME, PACKAGE_PYTHON_NAME + ".*"]

# Set the URL for which THIS VERSION of the package can be downloaded.
# See also:
#   - https://packaging.python.org/specifications/core-metadata/#download-url
PACKAGE_DOWNLOAD_URL = None


## Internal Constants - DO NOT EDIT
## -----------------------------------------------------------------------------
HERE = os.path.abspath(os.path.dirname(__file__))


### FUNCTIONS
### ============================================================================
def get_readme() -> Optional[Tuple[str, str]]:
    """Attempt to locate a readme based on common names.

    Returns a tuple containing the readme content and the readme content type.

    See also:
        - https://packaging.python.org/guides/distributing-packages-using-setuptools/#description
    """
    readmes = {
        "README": "text/plain",
        "README.md": "text/markdown",
        "README.txt": "text/plain",
        "README.rst": "text/x-rst",
    }
    for name, content_type in readmes.items():
        path = os.path.join(HERE, name)
        if not os.path.isfile(path):
            # Check for lowercase version of name just in case. (lol pun)
            path = os.path.join(HERE, name.lower())
            if not os.path.isfile(path):
                continue
        # Success we have a path
        with open(path) as readme_file:
            readme_content = readme_file.read()
        return (readme_content, content_type)

    return None


### SETUP
### ============================================================================
# Due to the nature of how arguments are handled in `setup` and the possibility
# of constants not being set, we selectively add them to a dict to use with
# `**kwargs` notation.
setup_extra_kwargs = {}  # pylint: disable=invalid-name

# Basic
if PACKAGE_URL:
    setup_extra_kwargs["url"] = PACKAGE_URL

if PACKAGE_AUTHOR:
    setup_extra_kwargs["author"] = PACKAGE_AUTHOR

if PACKAGE_AUTHOR_EMAIL:
    setup_extra_kwargs["author_email"] = PACKAGE_AUTHOR_EMAIL

if PACKAGE_DEPENDENCIES:
    setup_extra_kwargs["install_requires"] = PACKAGE_DEPENDENCIES

# Intermediate
if PACKAGE_ENTRY_POINTS:
    setup_extra_kwargs["entry_points"] = PACKAGE_ENTRY_POINTS

if PACKAGE_EXTRA_DEPENDENCIES:
    setup_extra_kwargs["extra_requires"] = PACKAGE_EXTRA_DEPENDENCIES

if INCLUDE_PACKAGE_DATA is not None:
    setup_extra_kwargs["package_data"] = INCLUDE_PACKAGE_DATA

if PACKAGE_DATA_FILES:
    setup_extra_kwargs["data_files"] = PACKAGE_DATA_FILES

if EXCLUDE_PACKAGE_DATA:
    setup_extra_kwargs["exclude_package_data"] = EXCLUDE_PACKAGE_DATA

if PACKAGE_KEYWORDS:
    setup_extra_kwargs["keywords"] = PACKAGE_KEYWORDS

if PACKAGE_MAINTAINER:
    setup_extra_kwargs["maintainer"] = PACKAGE_MAINTAINER

if PACKAGE_MAINTAINER_EMAIL:
    setup_extra_kwargs["maintainer_email"] = PACKAGE_MAINTAINER_EMAIL

if PACKAGE_PROJECT_URLS:
    setup_extra_kwargs["project_urls"] = PACKAGE_PROJECT_URLS

if PACKAGE_LICENCE:
    setup_extra_kwargs["licence"] = PACKAGE_LICENCE

# Advanced
if ZIP_SAFE is not None:
    setup_extra_kwargs["zip_safe"] = ZIP_SAFE

if PACKAGE_DOWNLOAD_URL:
    setup_extra_kwargs["download_url"] = PACKAGE_DOWNLOAD_URL

# Other
readme = get_readme()  # pylint: disable=invalid-name
if readme is not None:
    setup_extra_kwargs["long_description"] = readme[0]
    setup_extra_kwargs["long_description_content_type"] = readme[1]

# Do setup
setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description=PACKAGE_DESCRIPTION,
    classifiers=PACKAGE_CLASSIFIERS,
    python_requires=PYTHON_VERSIONS,
    package_dir={"": "src"},
    packages=find_packages("src", FIND_PACKAGES_EXCLUDE, FIND_PACKAGES_INCLUDE),
    **setup_extra_kwargs,
)
