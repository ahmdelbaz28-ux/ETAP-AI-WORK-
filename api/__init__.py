# API routers are imported explicitly by api/routes.py to avoid
# eager loading of all modules on any import of api.*
#
# Note: datetime.UTC (3.11+) and typing.Annotated (3.9+) are always
# available on the project's supported Python versions (>=3.12).
# The legacy polyfills were removed to avoid mutating sys.modules
# which can cause subtle breakage with C-accelerated typing in 3.13+.
