import socket
from unittest.mock import patch, MagicMock
from max_roku.discover import discover_roku_ip


def test_discover_roku_ip_success():
    """Test successful discovery of a Roku device."""

    # 1. Arrange: Create a mock socket
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # 2. Arrange: Define the fake response the Roku would send back
        # We need a valid-looking location header for your regex to match
        fake_response = b"HTTP/1.1 200 OK\r\nlocation: http://192.168.1.15:8060/description.xml\r\n\r\n"
        mock_socket.recvfrom.return_value = (fake_response, ("192.168.1.15", 1900))

        # 3. Act
        ip = discover_roku_ip()

        # 4. Assert
        assert ip == "192.168.1.15"
        mock_socket.sendto.assert_called()


def test_discover_roku_ip_timeout():
    """Test that discovery correctly handles a timeout."""

    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # 1. Arrange: Force recvfrom to raise a socket.timeout
        # This simulates the Roku never responding
        mock_socket.recvfrom.side_effect = socket.timeout

        # 2. Act
        ip = discover_roku_ip()

        # 3. Assert
        assert ip is None
        # Verify that we actually called recvfrom and it triggered our timeout
        mock_socket.recvfrom.assert_called()
