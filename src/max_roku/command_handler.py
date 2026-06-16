from max_roku.catalog import NETFLIX_APP_ID

class CommandHandler:
    def __init__(self, roku_controller):
        self.roku = roku_controller

        self.commands = {
            '?': lambda _: print(f"State: {self.roku.get_media_player_state()}"),
            'back': lambda _: self.roku.press_back(),
            'down': lambda _: self.roku.press_down(),
            'fwd' : lambda _: self.roku.press_fwd(),
            'home': lambda _: self.roku.press_home(),
            'instantreplay': lambda _: self.roku.press_instant_replay(),
            'launch': self.handle_launch,
            'left': lambda _: self.roku.press_left(),
            'pause': lambda _: self.roku.press_pause(),
            'playpause': lambda _: self.roku.press_play_pause(),
            'restart': self.handle_restart,
            'right': lambda _: self.roku.press_right(),
            'rev': lambda _: self.roku.press_rev(),
            'select': lambda _: self.roku.press_select(),
            'up': lambda _: self.roku.press_up(),
        }

    def handle_launch(self, args):
        if not args:
            print("Usage: launch <app_id> [content_id] [content_type]")
            return

        content_id = args[0] if len(args) > 0 else None
        content_type = args[1] if len(args) > 1 else None
        self.roku.launch_app(NETFLIX_APP_ID, content_id, content_type)

    def handle_restart(self, args):
        pause = False
        if args and args[0].lower() in ['pause']:
            pause = True

        return self.roku.restart_current(pause)


    def process(self, user_input: str) -> bool:
        """
                Parses user input, executes the command, and returns True.
                Returns False if the user wants to exit.
                """
        if not user_input:
            return True

        parts = user_input.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == 'exit':
            print("Exiting Remote Control.")
            return False

        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            print(f"Unknown command: '{cmd}'. Please try again.")

        return True

    def get_available_commands(self) -> str:
        """Dynamically returns a list of configured commands"""
        return ", ".join(list(self.commands.keys()) + ['exit'])