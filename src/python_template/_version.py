"""Version information for this package."""
### IMPORTS
### ============================================================================
## Standard Library

## Installed

## Application

### CONSTANTS
### ============================================================================
## Version Information - DO NOT EDIT
## -----------------------------------------------------------------------------
# These variables will be set during the build process. Do not attempt to edit.
PACKAGE_VERSION = ""
BUILD_VERSION = ""
BUILD_GIT_HASH = ""
BUILD_GIT_HASH_SHORT = ""
BUILD_GIT_BRANCH = ""
BUILD_TIMESTAMP = ""
BUILD_DATETIME = ""

## Version Information Templates
## -----------------------------------------------------------------------------
# You can customise the templates used for version information here.
VERSION_INFO_TEMPLATE_SHORT = "{BUILD_VERSION}"
VERSION_INFO_TEMPLATE = "{PACKAGE_VERSION} ({BUILD_VERSION})"
VERSION_INFO_TEMPLATE_LONG = (
    "{PACKAGE_VERSION} ({BUILD_VERSION}) ({BUILD_GIT_BRANCH}@{BUILD_GIT_HASH_SHORT})"
)
VERSION_INFO_TEMPLATE_FULL = (
    "{PACKAGE_VERSION} ({BUILD_VERSION})\n"
    "{BUILD_GIT_BRANCH}@{BUILD_GIT_HASH}\n"
    "Built: {BUILD_DATETIME}"
)

### FUNCTIONS
### ============================================================================
def get_version_info_short() -> str:
    return VERSION_INFO_TEMPLATE_SHORT.format(vars())


def get_version_info() -> str:
    return VERSION_INFO_TEMPLATE.format(vars())


def get_version_info_long() -> str:
    return VERSION_INFO_TEMPLATE_LONG.format(vars())


def get_version_info_full() -> str:
    return VERSION_INFO_TEMPLATE_FULL.format(vars())
