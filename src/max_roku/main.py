import argparse

from max_roku.command_handler import CommandHandler
from max_roku.discover import discover_roku_ip
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

    print(f"Targeting Roku at: {roku_ip}")
    roku = RokuController(roku_ip)

    handler = CommandHandler(roku)

    print("\n--- Interactive Roku Remote Active ---")
    print(f"Available commands: {handler.get_available_commands()}")

    while True:
        user_input = input("\nEnter command: ").strip().lower()
        if not handler.process(user_input):
            break

# --- Usage Example ---
if __name__ == "__main__":
    main()
