import os
import sys
import pytest
from loguru import logger
import time
import asyncio

from unittest.mock import AsyncMock, MagicMock

# 1. Remove the default console output globally
logger.remove()


@pytest.fixture(autouse=True)
def setup_test_specific_loguru(request):
    # 2. READ THE ENVIRONMENT VARIABLE
    # Defaults to "DEBUG" if the variable is not set.
    # .upper() ensures it accepts 'debug', 'Debug', or 'DEBUG'.
    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()

    # 3. Build the mirrored subdirectory paths
    fspath = request.node.fspath
    rel_path = os.path.relpath(fspath, start=os.getcwd())
    test_dir_structure = os.path.dirname(rel_path)
    target_log_dir = os.path.join("test_logs", test_dir_structure)
    os.makedirs(target_log_dir, exist_ok=True)

    # 4. Create the unique log filename
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    log_file_path = os.path.join(target_log_dir, f"{test_name}.log")

    # 5. Set up the memory buffer
    failure_buffer = []

    def buffer_sink(message):
        failure_buffer.append(message)

    # 6. Add BOTH sinks using the dynamic log_level variable
    log_format = "{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}"
    file_id = logger.add(log_file_path, mode="w", format=log_format, level=log_level)
    buffer_id = logger.add(buffer_sink, format=log_format, level=log_level)

    # 7. Let the test run
    yield

    # 8. Clean up the Loguru handlers immediately
    logger.remove(file_id)
    logger.remove(buffer_id)

    # 9. Check if any phase of the test failed or errored out
    rep_status = getattr(request.node, "rep_status", {})
    if any(report.failed or report.outcome == "error" for report in rep_status.values()):
        sys.stderr.write(f"\n--- LOGS FOR FAILED TEST: {request.node.name} ({log_level} LEVEL) ---\n")
        for log_entry in failure_buffer:
            sys.stderr.write(log_entry)
        sys.stderr.write("-----------------------------------------\n")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if not hasattr(item, "rep_status"):
        item.rep_status = {}
    item.rep_status[rep.when] = rep


def pytest_configure(config):
    """
    Executes at the absolute inception of the Pytest run, BEFORE any test
    or app modules are imported. Swaps out core sleep behaviors globally.
    """
    if config.getoption("--hw", default=False):
        return

    # 1. Force environment parameters to skip the 3-second discovery UDP scan
    import os
    if not os.environ.get("ROKU_IP"):
        os.environ["ROKU_IP"] = "127.0.0.1"

    # 2. Mutate the foundation modules to instantly return mock containers.
    # Every module loaded after this point will pull the mock instead of the real delay!
    asyncio.sleep = AsyncMock()

    print("\n⚡ Mock Mode Active: Fast-forwarding all test and app delays instantly!")
