# Positional Voice Chat for WoW 3.3.5

## Requirements
- Mumble 1.3.4
- The `wow3.dll` plugin, provided here.

## Instructions
1. Install Mumble 1.3.4
2. Place the WoW3.dll into the Mumble plugin folder `C:\Program Files (x86)\Mumble\Versions\1.3.4\plugins` or `%AppData%\Roaming\Mumble\Plugins`
3. In your Mumble `Audio Output` settings, enable the `Positional Audio` option
4. In your Mumble `Plugins` settings:
    - Ensure the `World of Warcraft (x86) version 3.3.5a.12340` plugin is present and enabled
    - Ensure the `Link to Game and Transmit Position` option is enabled
    - Ensure the other `World of Warcraft` plugin (made for a later version) is disabled
5. Connect to a Mumble server with others using the same plugin
6. Confirm the message `World of Warcraft 3.3.5a linked` appears in the Mumble chat pane (this can take a few moments to detect)

## Todo
Currently the plugin contains the context of the player (their map ID) but the Mumble server will not automatically manage users (move users or generate channels) without, as an example, a [Mumble Moderator](https://github.com/mumble-voip/mumo/tree/master) script. Without a moderation system users will all be in the same channel and their audio will be heard when near another player within range of their coordinates, regardless of which map they're on or instance they're in.
