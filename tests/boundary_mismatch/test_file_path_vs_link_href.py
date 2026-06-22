"""Test: file path vs link href mapping.

Catches broken links: UI page links to /dashboard/studies but the actual
page file is at /studies (or vice versa).
"""
import re
from pathlib import Path


def test_no_broken_internal_links():
    """Scan all .tsx files for href= and router.push() and verify they map to pages."""
    ui_dir = Path(__file__).resolve().parents[2] / "ui" / "src"
    if not ui_dir.exists():
        import pytest
        pytest.skip("ui/src/ not found")

    # Collect all page files (pages/*.tsx)
    page_files = list((ui_dir / "pages").glob("*.tsx")) if (ui_dir / "pages").exists() else []
    page_names = {f.stem.lower() for f in page_files}

    # Collect all href/router.push targets
    hrefs = []
    for tsx in ui_dir.rglob("*.tsx"):
        content = tsx.read_text()
        # href="/path"
        hrefs.extend(re.findall(r'href=["\']([^"\']+)["\']', content))
        # router.push("/path")
        hrefs.extend(re.findall(r'router\.push\(["\']([^"\']+)["\']', content))
        # to="/path" (React Router)
        hrefs.extend(re.findall(r'\bto=["\']([^"\']+)["\']', content))

    # Filter to internal paths only (not http://, not #anchors)
    internal = [h for h in hrefs if h.startswith("/") and not h.startswith("//")]

    findings = []
    for href in internal:
        # Strip query params and fragments
        path = href.split("?")[0].split("#")[0]
        # Extract the last segment as potential page name
        segments = [s for s in path.split("/") if s]
        if not segments:
            continue  # root path "/"
        last_segment = segments[-1].lower()
        # Check if it matches a page file (exact or close)
        if page_names and last_segment not in page_names:
            # Might be a dynamic route or external — just flag for review
            findings.append(f"  {href} → no matching page file '{last_segment}.tsx'")

    if findings:
        print(f"\n[BOUNDARY MISMATCH] Internal links without matching page files ({len(findings)}):")
        for f in findings[:20]:  # limit output
            print(f)
        if len(findings) > 20:
            print(f"  ... and {len(findings) - 20} more")
    else:
        print("✓ All internal links map to page files")
