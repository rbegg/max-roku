# Roku for Max AI Agent
Module that use Roku ECP commands and deep-links to launch content
## Limitations
- Currently, the only supported app is Netflix (appID=12)
- Roku ECP is meant for virtual remote apps and cannot receive any
details about the content that may be playing
## Netflix account setup
- The account must be logged in manually and will stay logged in 
if used frequently enough
- In account settings, change the 'auto-play next episode' setting
to off for the profile being managed


## Project Structure
```
max-roku/
├── src/
│   └── max_roku/
│       ├── main.py               # CLI Entry point and interaction loop
│       ├── roku_controller.py    # ECP API Driver (The Receiver)
│   	├── command_handler.py    # Command Pattern implementation (The Invoker)
│       ├── discover.py           # SSDP discovery logic
│       ├── catalog.py            # Content and app metadata
│       └── README.md             # Project documentation
├── Pipfile                       # Dependency management (Python)
└── Pipfile.lock                  # Deterministic builds
```