import os

# comma-separated list of regexps that match blocking function names in your project
BLOCKING_FUNCTION_NAMES = os.getenv("BLOCKING_FUNCTION_NAMES") or ""

# comma-separated list of regexps that match function names that should be skipped
SKIP_FUNCTIONS = os.getenv("SKIP_FUNCTIONS") or ""

# comma-separated list of regexps that match module names that should be skipped
SKIP_MODULES = os.getenv("SKIP_MODULES") or ""

# comma-separated list of regexps that match decorator names that should be skipped
SKIP_DECORATED = os.getenv("SKIP_DECORATED") or ""
