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
        sock.sendto(ssdp_msg, ('239.255.255.250', 1900))

        while True:
            data, addr = sock.recvfrom(1024)
            response = data.decode('utf-8', errors='ignore')

            # Look for the 'location' header in the response
            # It usually looks like: location: http://192.168.1.15:8060/description.xml
            match = re.search(r'location: (http://[0-9.]+:[0-9]+)', response, re.IGNORECASE)
            if match:
                found_url = match.group(1)
                # Extract just the IP address from the URL
                return found_url.split(':')[0]
    except socket.timeout:
        return None
    except Exception as e:
        print(f"Discovery error: {e}")
        return None
    finally:
        sock.close()