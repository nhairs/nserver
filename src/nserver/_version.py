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

## Version Information Strings
## -----------------------------------------------------------------------------
VERSION_INFO_SHORT = f"{BUILD_VERSION}"
VERSION_INFO = f"{PACKAGE_VERSION} ({BUILD_VERSION})"
VERSION_INFO_LONG = (
    f"{PACKAGE_VERSION} ({BUILD_VERSION}) ({BUILD_GIT_BRANCH}@{BUILD_GIT_HASH_SHORT})"
)
VERSION_INFO_FULL = (
    f"{PACKAGE_VERSION} ({BUILD_VERSION})\n"
    f"{BUILD_GIT_BRANCH}@{BUILD_GIT_HASH}\n"
    f"Built: {BUILD_DATETIME}"
)
