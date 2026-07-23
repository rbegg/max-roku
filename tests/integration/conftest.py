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
def mock_roku_network(request):
    """
    Globally intercepts all outbound network calls via httpx to simulate
    hardware state timelines deterministically across all parameterized runs.
    """
    is_hw = bool(request.config.getoption("--hw", default=False))
    if is_hw:
        yield
        return

    # 1. Non-blocking AsyncMock loops: Optimize execution times instantly
    mocker = request.getfixturevalue("mocker")
    mocker.patch("asyncio.sleep")

    # 2. Chronological timeline parser tracking state progression
    def get_mock_value(key) -> str:
        state_data = MOCK_ROKU_STATE[key]
        if isinstance(state_data, list):
            if len(state_data) == 1:
                state_data = state_data[0]
            elif len(state_data) > 1:
                state_data = state_data.pop(0)
            else:
                raise ValueError(f"Invalid state data for key: {key}")
            return state_data
        return state_data

    # 3. Request interceptor routing logic mimicking Roku hardware ECP
    def dynamic_mock_send(request_obj: httpx.Request, *args, **kwargs) -> httpx.Response:
        url_path = str(request_obj.url)

        # Handle active app querying path
        if "query/active-app" in url_path:
            app_id = get_mock_value("plugin_id")
            app_name = get_mock_value("plugin_name")
            dynamic_xml = f"""<active-app>
                <app id="{app_id}" type="appl" version="1.0.0" ui-location="{app_id}">{app_name}</app>
            </active-app>"""
            return httpx.Response(status_code=200, text=dynamic_xml, request=request_obj)

        # Handle media player state querying loops
        if "query/media-player" in url_path:
            player_state = get_mock_value("player_state")
            position = get_mock_value("player_position_ms")
            app_id = get_mock_value("plugin_id")
            player_xml = f"""<player error="false" state="{player_state}">
                <plugin id="{app_id}" version="1.0.0" />
                <position>{position}</position>
            </player>"""
            return httpx.Response(status_code=200, text=player_xml, request=request_obj)

        # Catch-all success loop for all actions (POST /launch, POST /keypress commands)
        return httpx.Response(status_code=200, text="<success/>", request=request_obj)

    # 4. Global Interception Link
    # This forces ANY AsyncClient created anywhere in your backend logic to bypass real sockets
    mocker.patch.object(httpx.AsyncClient, "send", side_effect=dynamic_mock_send)


    yield  # Let the parameterized tests run seamlessly


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
