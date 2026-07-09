import pytest
from fastapi.testclient import TestClient
import httpx
from loguru import logger

# Import your actual FastAPI application from your main app script
from max_roku.main import roku_app

APP_STATE_NETFLIX = """
<active-app>
        <app id="12" type="appl" version="80.2523.1521022" ui-location="12">Netflix</app>
</active-app>"""

APP_STATE_HOME = """
<active-app>
        <app id="562859" type="home" version="14.10.5" ui-location="home">Roku Dynamic Menu</app>
</active-app>
"""

# Pristine baseline defaults for mock execution
DEFAULT_ROKU_STATE = {
    "plugin_id": ["12"],  # 12 is Netflix
    "plugin_name": ["Netflix"],
    "player_state": ["play"],
    "player_position_ms": ["8000"],  # 8 seconds played
    "app_state": [APP_STATE_NETFLIX]
}

# The active container that your tests can safely mutate in-flight
MOCK_ROKU_STATE: dict[str, list[str] | str] = {k: list(v) for k, v in DEFAULT_ROKU_STATE.items()}


def pytest_addoption(parser):
    """Registers the custom --hw flag to switch targets."""
    parser.addoption(
        "--hw",
        action="store_true",
        default=False,
        help="Execute tests against physical Roku hardware."
    )
    parser.addoption(
        "--manual",
        action="store_true",
        default=False,
        help="If executing tests against physical Roku hardware, prompt for integration verification."
    )


@pytest.fixture
def is_hw(request):
    """Fixture to let tests cleanly branch conditional integration validation steps."""
    return request.config.getoption("--hw")

@pytest.fixture
def manual_confirmation(request):
    """Fixture to let tests cleanly branch conditional integration validation steps."""
    return request.config.getoption("--manual")


@pytest.fixture(autouse=True)
def mock_roku_network(request, mocker, ):
    """
    Autouse interceptor that patches all outgoing httpx calls globally.
    If --hw is targeted, it leaves network transport unmodified.
    """
    if request.config.getoption("--hw"):
        yield
        return

    def dynamic_mock_send(request_obj,*_args, **_kwargs):
        url_path = str(request_obj.url.path)

        # Utility helper to pop values chronologically if configured as a sequence list
        def get_mock_value(key) -> str:
            state_data = MOCK_ROKU_STATE[key]
            if isinstance(state_data, list):
                return state_data.pop(0) if len(state_data) > 1 else state_data[0]
            else:
                return state_data

        # 1. Mock the /query/active-app route
        if "get-active-app" in url_path:
            mock_xml = get_mock_value('app_state')
            return httpx.Response(status_code=200, text=mock_xml, request=request_obj)

        # 2. Mock the /query/media-player route
        elif "query/media-player" in url_path:
            mock_xml = f"""
            <player state="{get_mock_value('player_state')}" error="false">
                <plugin id="{get_mock_value('plugin_id')}" name="{get_mock_value('plugin_name')}" />
                <format audio="aac_adts" video="av1" captions="none" drm="none" />
                <position>143549 ms</position>
            </player>"""
            return httpx.Response(status_code=200, text=mock_xml, request=request_obj)

        # 3. Default catch-all for keypress, launch, and macro installations
        return httpx.Response(status_code=200, text="", request=request_obj)

    # Inject our dynamic router directly into the underlying httpx network client engine
    mocker.patch.object(httpx.AsyncClient, "send", side_effect=dynamic_mock_send)

    mocker.patch("asyncio.sleep")

    try:
        yield  # Run the test case
    finally:
        # Strict Teardown cycle: Cleanly scrub and reset modifications to isolate all cases
        global MOCK_ROKU_STATE
        MOCK_ROKU_STATE = {k: list(v) for k, v in DEFAULT_ROKU_STATE.items()}


@pytest.fixture
def client(request):
    """Provides a virtual TestClient while leaving app routers and startup lifespan hooks intact."""
    with TestClient(roku_app) as test_client:
        try:
            yield test_client
        finally:
            # 2. Teardown Phase: Runs *immediately* when the test case ends
            is_hw = bool(request.config.getoption("--hw", default=False))

            if is_hw:
                logger.info("\n🧹 Test complete. Returning Roku safely back to Home screen...")
                try:
                    # Execute your home route cleanup directly on the active client instance
                    cleanup_response = test_client.post("press/Home")
                    assert cleanup_response.status_code == 200, (
                        f"❌ Mandatory Teardown Failure: Physical Roku rejected the Home command! "
                        f"Status: {cleanup_response.status_code}, Payload: {cleanup_response.text}"
                    )
                except AssertionError:
                    # Let intentional assertion failures bubble up to Pytest!
                    raise
                except Exception as e:
                    logger.error(f"⚠️ Warning: Automated Home cleanup failed: {e}")
