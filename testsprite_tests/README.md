# TestSprite Tests

This directory contains configuration and artifacts for TestSprite automated testing.

## Structure

```
testsprite_tests/
  tmp/
    config.json       # TestSprite runtime configuration
    prd_files/        # Generated PRD documents
    test_plans/       # Generated test plans (frontend + backend)
    reports/          # Test execution reports
    code/             # Generated test code
    screenshots/      # Test screenshots
```

## Workflow

1. TestSprite scans the codebase → generates `code_summary.json`
2. Creates a `standard_prd.json` from the analysis
3. Generates `frontend_test_plan.json` and `backend_test_plan.json`
4. Produces test code and executes it
5. Reports are saved to `reports/`

Run from Cursor/VS Code: *"Help me test this project with TestSprite"*
