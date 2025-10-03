#!/usr/bin/env python3
"""
Manual sync utility for Hybrid Storage Backend.
Triggers an immediate sync from SQLite-vec to Cloudflare.

Usage:
    python sync_now.py [--db-path PATH] [--verbose]

Environment Variables:
    MCP_MEMORY_SQLITE_PATH: Override default database path
"""
import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Import from installed package (assumes package is installed in editable mode)
try:
    from dotenv import load_dotenv
    from mcp_memory_service.storage.factory import create_storage_instance
    from mcp_memory_service.storage.hybrid import HybridMemoryStorage
    from mcp_memory_service.config import SQLITE_VEC_PATH
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    logger.error("Make sure the package is installed: pip install -e .")
    sys.exit(1)


async def main(db_path: str | None = None, verbose: bool = False):
    """
    Run immediate sync.

    Args:
        db_path: Optional path to SQLite database. If not provided,
                uses MCP_MEMORY_SQLITE_PATH env var or default config.
        verbose: Enable verbose error reporting with full tracebacks.
    """
    # Load environment variables
    load_dotenv()

    logger.info("🔄 Starting manual sync...")

    # Determine database path
    sqlite_path = Path(db_path or os.getenv('MCP_MEMORY_SQLITE_PATH') or SQLITE_VEC_PATH)

    if not sqlite_path.exists():
        logger.error(f"❌ Database not found: {sqlite_path}")
        return 1

    logger.info(f"📁 Using database: {sqlite_path}")

    # Create storage instance
    try:
        storage = await create_storage_instance(str(sqlite_path))
    except Exception as e:
        logger.error(f"❌ Failed to create storage instance: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1

    # Type-safe check for hybrid storage
    if not isinstance(storage, HybridMemoryStorage):
        logger.error("❌ Not a hybrid backend - sync not available")
        logger.error(f"   Found: {storage.__class__.__name__}")
        return 1

    # Get sync status before
    try:
        status_before = await storage.get_sync_status()
        logger.info(f"📊 Before sync:")
        logger.info(f"   Queue size: {status_before['queue_size']}")
        logger.info(f"   Cloudflare available: {status_before['cloudflare_available']}")
    except Exception as e:
        logger.warning(f"⚠️  Could not get sync status: {e}")

    # Trigger immediate sync
    logger.info("\n⏳ Triggering sync...")
    try:
        result = await storage.force_sync()
        logger.info("✅ Sync completed successfully!")
        logger.info(f"   Synced: {result.get('synced_to_secondary', 0)} operations")
        logger.info(f"   Duration: {result.get('duration', 0):.2f}s")
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1

    # Get sync status after
    try:
        status_after = await storage.get_sync_status()
        logger.info(f"\n📊 After sync:")
        logger.info(f"   Queue size: {status_after['queue_size']}")
        logger.info(f"   Failed operations: {status_after['failed_operations']}")
    except Exception as e:
        logger.warning(f"⚠️  Could not get final sync status: {e}")

    return 0


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Manual sync utility for Hybrid Storage Backend"
    )
    parser.add_argument(
        '--db-path',
        type=str,
        help='Path to SQLite database (default: from config or env)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose error reporting with full tracebacks'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(db_path=args.db_path, verbose=args.verbose))
    sys.exit(exit_code)
