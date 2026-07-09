import socket
import re


def discover_roku_ip():
    """
    Search for Roku devices on the local network using SSDP.
    Returns the IP address if found, otherwise None.
    """
    ssdp_msg = (
        'M-SEARCH * HTTP/1.1\r\n'
        'Host: 239.255.255.250:1900\r\n'
        'Man: "ssdp:discover"\r\n'
        'ST: roku:ecp\r\n'
        '\r\n'
    ).encode('utf-8')

    # Set up the UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(3)  # Wait up to 3 seconds for a response

    try:
        # Send the multicast search request
        # noinspection PyTypeChecker
        sock.sendto(ssdp_msg, ('239.255.255.250', 1900))

        while True:
            try:
                data, addr = sock.recvfrom(1024)
                response = data.decode('utf-8', errors='ignore')

                # Improved regex: explicitly looks for the location header,
                # followed by http://, and captures the IP segment before the colon.
                match = re.search(r'location: http://([\d.]+):', response, re.IGNORECASE)

                if match:
                    return match.group(1)
            except socket.timeout:
                print("Discovery timed out; no Roku device responded.")
                break
    finally:
        sock.close()

    return None