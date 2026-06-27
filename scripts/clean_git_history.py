#!/usr/bin/env python3
"""
Git History Cleanup Script
==========================

This script helps clean sensitive data from git history as mentioned in the technical debt.
Use this script to remove sensitive files from git history using BFG Repo-Cleaner.

Before running this script, ensure you have:
1. A backup of your repository
2. Java installed (for BFG)
3. Downloaded the BFG jar file from https://rtyley.github.io/bfg-repo-cleaner/
"""

import os
import subprocess
import sys


def run_git_command(cmd_parts, cwd='.'):
    """Run a git command and return the result."""
    try:
        # Use list form to avoid shell=True vulnerability
        result = subprocess.run(cmd_parts, capture_output=True, text=True, cwd=cwd)
        if result.returncode != 0:
            print(f"Error running command: {' '.join(cmd_parts)}")
            print(f"Error: {result.stderr}")
            return False, result.stderr
        return True, result.stdout
    except Exception as e:
        print(f"Exception running command: {' '.join(cmd_parts)}, Error: {e}")
        return False, str(e)

def clean_sensitive_files(repo_path, files_to_remove):
    """
    Clean sensitive files from git history.
    
    Args:
        repo_path: Path to the git repository
        files_to_remove: List of file patterns to remove from history
    """
    print("Starting git history cleanup...")
    print(f"Repository path: {repo_path}")
    print(f"Files to remove: {files_to_remove}")

    # Verify we're in a git repo
    if not os.path.exists(os.path.join(repo_path, '.git')):
        print("Error: Not a git repository")
        return False

    # Create a backup branch
    print("Creating backup branch...")
    success, output = run_git_command(["git", "status", "--porcelain"], repo_path)
    if success and output.strip():
        print("Warning: Uncommitted changes detected. Please commit or stash them.")
        return False

    success, output = run_git_command(["git", "branch"], repo_path)
    if "backup-pre-cleanup" not in output:
        success, output = run_git_command(["git", "checkout", "-b", "backup-pre-cleanup"], repo_path)
        if not success:
            print(f"Failed to create backup branch: {output}")
            return False
        print("Backup branch 'backup-pre-cleanup' created successfully.")
    else:
        print("Backup branch already exists.")

    # Build BFG command
    bfg_jar = "bfg-1.14.0.jar"  # Default BFG jar name, adjust as needed
    if not os.path.exists(bfg_jar):
        print(f"Error: BFG jar file not found: {bfg_jar}")
        print("Download BFG from: https://rtyley.github.io/bfg-repo-cleaner/")
        print("Place the jar file in the repository root or update this script.")
        return False

    # Create deletion rules
    deletion_args = []
    for file_pattern in files_to_remove:
        deletion_args.extend(["--delete-files", file_pattern])

    if not deletion_args:
        print("No files to delete")
        return False

    # Use subprocess with list form to avoid shell=True vulnerability
    bfg_cmd_parts = ["java", "-jar", bfg_jar] + deletion_args

    print(f"Running BFG command: {' '.join(bfg_cmd_parts)}")
    try:
        result = subprocess.run(
            bfg_cmd_parts,
            capture_output=True,
            text=True,
            cwd=repo_path
        )

        if result.returncode != 0:
            print(f"BFG command failed: {result.stderr}")
            return False

        print("BFG completed successfully!")
        print(result.stdout)
    except Exception as e:
        print(f"Error running BFG: {e}")
        return False

    # Clean up refs and optimize
    print("Cleaning up git refs...")
    commands = [
        ["git", "reflog", "expire", "--expire=now", "--all"],
        ["git", "gc", "--prune=now", "--aggressive"]
    ]

    for cmd_parts in commands:
        print(f"Running: {' '.join(cmd_parts)}")
        success, output = run_git_command(cmd_parts, repo_path)
        if not success:
            print(f"Failed to run: {' '.join(cmd_parts)}, Error: {output}")
            return False

    print("Git history cleanup completed!")
    print("\nImportant: You will need to force push to update remote repository:")
    print("git push --force-with-lease origin <your_branch_name>")
    print("\nAlso inform team members to re-clone the repository after pushing changes.")

    return True

def main():
    """Main function to execute the git history cleanup."""
    # Get repository path
    repo_path = os.getcwd()

    # Files to remove from history (as mentioned in technical debt)
    files_to_remove = [
        ".mcp.json",
        "*.pem",  # SSL certificates
        "*.key",   # Private keys
        "*.p12",  # PKCS#12 files
        "config/secrets/*",
        "*.env",
        "*.config",
    ]

    print("Git History Cleanup Tool")
    print("="*50)
    print("This script will remove sensitive files from git history.")
    print("Make sure you have a backup before proceeding!\n")

    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Operation cancelled.")
        return

    success = clean_sensitive_files(repo_path, files_to_remove)
    if success:
        print("\nCleanup completed successfully!")
        print("Remember to:")
        print("1. Push changes to remote: git push --force-with-lease origin <branch>")
        print("2. Inform team members to re-clone the repository")
    else:
        print("\nCleanup failed. Check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
