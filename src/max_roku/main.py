import argparse


from max_roku.discover import discover_roku_ip
from max_roku.catalog import Catalog, NETFLIX_APP_ID, NETFLIX_CATALOG
from max_roku.roku_controller import RokuController


def main():
    parser = argparse.ArgumentParser(description="Control a Roku device via ECP.")
    parser.add_argument(
        "-i", "--ip",
        help="IP address of the Roku device. If not provided, will attempt discovery via SSDP."
    )
    args = parser.parse_args()

    roku_ip = args.ip

    if not roku_ip:
        print("No IP address provided. Searching for Roku device on the network via SSDP...")
        roku_ip = discover_roku_ip()
        if not roku_ip:
            print("Error: No Roku device could be identified. Please check your network or provide the IP manually.")
            return

    catalog = Catalog(NETFLIX_CATALOG)

    print(f"Targeting Roku at: {roku_ip}")
    roku = RokuController(roku_ip)

    print("\n--- Interactive Roku Remote Active ---")
    print("Available commands: up, down, home, back, select, left, right, playpause, exit")

    while True:
        # Get user input and clean it up
        cmd = input("\nEnter command: ").strip().lower()

        if cmd == 'exit':
            print("Exiting Remote Control.")
            break
        elif cmd == 'up':
            roku.launch_app(NETFLIX_APP_ID, *catalog.next())
        elif cmd == 'down':
            roku.launch_app(NETFLIX_APP_ID, *catalog.prev())
        elif cmd == 'home':
            roku.press_home()
        elif cmd == 'back':
            roku.press_back()
        elif cmd == 'play':
            roku.launch_app(NETFLIX_APP_ID, *catalog.current())
        elif cmd == '?':
            print(f"State: {roku.get_media_player_state()}")
        elif cmd == 'select':
            roku.press_select()
            continue
        else:
            print(f"Unknown command: '{cmd}'. Please try again.")


# --- Usage Example ---
if __name__ == "__main__":
    main()
