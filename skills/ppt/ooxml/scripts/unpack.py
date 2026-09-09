#!/usr/bin/env python3
# NOSONAR
"""Unpack and format XML contents of Office files (.docx, .pptx, .xlsx)"""

import argparse
import random
import zipfile
from pathlib import Path

import defusedxml.minidom


def main():
    parser = argparse.ArgumentParser(description="Unpack an Office file into a directory")
    parser.add_argument("office_file", help="Office file (.docx/.pptx/.xlsx)")
    parser.add_argument("output_dir", help="Output directory")
    args = parser.parse_args()
    unpack_document(args.office_file, args.output_dir)


def unpack_document(input_file, output_dir):
    """Unpack an Office file into a directory and pretty-print all XML files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)  # NOSONAR - pythonsecurity:S8707

    with zipfile.ZipFile(input_file) as zf:
        resolved_output = output_path.resolve()
        for member in zf.infolist():
            member_path = (output_path / member.filename).resolve()
            if not str(member_path).startswith(str(resolved_output)):
                raise ValueError(f"ZipSlip detected in archive member: {member.filename}")
            zf.extract(member, output_path)

    for pattern in ["*.xml", "*.rels"]:
        for xml_file in output_path.rglob(pattern):
            pretty_print_xml(xml_file)

    # For .docx files, suggest an RSID for tracked changes
    if str(input_file).endswith(".docx"):
        suggested_rsid = "".join(random.choices("0123456789ABCDEF", k=8))  # NOSONAR - python:S2245
        print(f"Suggested RSID for edit session: {suggested_rsid}")


def pretty_print_xml(xml_file):
    """Pretty-print a single XML file in place."""
    content = xml_file.read_text(encoding="utf-8")
    dom = defusedxml.minidom.parseString(content)
    xml_file.write_bytes(dom.toprettyxml(indent="  ", encoding="ascii"))


if __name__ == "__main__":
    main()
