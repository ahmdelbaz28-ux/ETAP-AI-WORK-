#!/usr/bin/env python3
"""
Script to start the Celery worker for the Engineering Service.
"""
import sys


def main():
    """Start the Celery worker."""
    # Import the Celery app
    from worker.celery_app import app

    # Parse command-line arguments
    argv = sys.argv[1:] if len(sys.argv) > 1 else ['-A', 'worker.celery_app', 'worker', '--loglevel=info']

    # Start the worker
    try:
        app.start(argv=argv)
    except KeyboardInterrupt:
        print("Celery worker stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting Celery worker: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
