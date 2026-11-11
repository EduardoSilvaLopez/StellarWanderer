# Sounds

Every sound the game plays, what it is for, and where it is played. The sounds are files in `common/resources/sounds`
(WAV or MP3), keyed in `SOUNDS` in [common/audio.py](../audio.py). The WAV placeholders are made by
[tools/generate_sounds.py](../../tools/generate_sounds.py).

## How to replace a sound

- **Easiest:** put a file with the same file name in `common/resources/sounds`. It takes the place of the placeholder with no
  code change.
- **Different file name:** change the `file` of the key in `SOUNDS` ([common/audio.py](../audio.py)).
- **Volume or silence rules:** change the key's `volume` and `silent_when_fast` in `SOUNDS`.
- **Careful:** running [tools/generate_sounds.py](../../tools/generate_sounds.py) again overwrites the WAVs in that folder.
  Keep your own replacements elsewhere, or do not run it.
- `thrust` and `attitude` share `thrust.wav`: replacing it changes both.

## Table

"Fast" means "silent when time is compressed above x1" (the `silent_when_fast` flag). "Loop" means started and stopped
with `set_loop`.

| Key | File | Volume | Fast | What it is for | Where it is played | Replace the sound in |
|---|---|---|---|---|---|---|
| `ui_open` | ui_open.wav | 0.5 | no | A dialog opens (default for every message and for the settlement screen) | [common/dialogs/dialog.py:34](../dialogs/dialog.py#L34), [common/dialogs/settlement_screen.py:187](../dialogs/settlement_screen.py#L187), [common/dialogs/messages.py:29](../dialogs/messages.py#L29), played by [main.py:130](../../main.py#L130) | `ui_open.wav` |
| `ui_close` | ui_close.wav | 0.5 | no | A dialog closes, or Esc / right-click goes back | [common/dialogs/dialog.py:35](../dialogs/dialog.py#L35), [common/dialogs/settlement_screen.py:188](../dialogs/settlement_screen.py#L188), [common/dialogs/mission_board_dialog.py:193](../dialogs/mission_board_dialog.py#L193), played by [main.py:147](../../main.py#L147) and [main.py:433](../../main.py#L433) | `ui_close.wav` |
| `ui_click` | ui_click.wav | 0.5 | no | A button or a row is pressed | [common/dialogs/starting_dialog.py:302](../dialogs/starting_dialog.py#L302), [starting_dialog.py:363](../dialogs/starting_dialog.py#L363), [starting_dialog.py:369](../dialogs/starting_dialog.py#L369), [starting_dialog.py:374](../dialogs/starting_dialog.py#L374), [staff_list.py:113](../dialogs/staff_list.py#L113), [staff_list.py:234](../dialogs/staff_list.py#L234), [settlement_screen.py:671](../dialogs/settlement_screen.py#L671), [settlement_screen.py:1056](../dialogs/settlement_screen.py#L1056), [mission_board_dialog.py:257](../dialogs/mission_board_dialog.py#L257), [chat_view.py:225](../dialogs/chat_view.py#L225), [chat_view.py:228](../dialogs/chat_view.py#L228), [chat_view.py:353](../dialogs/chat_view.py#L353), [chat_view.py:358](../dialogs/chat_view.py#L358) | `ui_click.wav` |
| `mission_taken` | mission_taken.wav | 0.6 | no | A mission is taken from the board | [galaxies/missions/mission_board.py:133](../../galaxies/missions/mission_board.py#L133) | `mission_taken.wav` |
| `mission_delivered` | mission_delivered.wav | 0.6 | no | A mission is delivered | [galaxies/missions/mission_board.py:144](../../galaxies/missions/mission_board.py#L144) | `mission_delivered.wav` |
| `failed` | failed.wav | 0.7 | no (an alert) | A mission fails ([galaxies/missions/mission.py:173](../../galaxies/missions/mission.py#L173)); a mine cannot be placed, and the scoop is refused above its speed, instead of the notification's own sound ([spaceships/ship.py:210](../../spaceships/ship.py#L210), [ship.py:536](../../spaceships/ship.py#L536)-[550](../../spaceships/ship.py#L550)); a mine refused by the settlement screen ([common/dialogs/settlement_screen.py:673](../dialogs/settlement_screen.py#L673), [settlement_screen.py:753](../dialogs/settlement_screen.py#L753)) | `failed.wav` |
| `notify` | notify.mp3 | 0.4 | no | A notification or warning (default of `Notification`); the advisor's change of advice | [spaceships/notification.py:31](../../spaceships/notification.py#L31), [spaceships/long_distance_advice.py:212](../../spaceships/long_distance_advice.py#L212) (played at [line 240](../../spaceships/long_distance_advice.py#L240)) | `notify.mp3` |
| `alert` | alert.mp3 | 0.7 | no | A CRITICAL notification (messages starting with `CRITICAL`); the navigation alert dialog | [spaceships/notification.py:31](../../spaceships/notification.py#L31), [spaceships/navigation.py:428](../../spaceships/navigation.py#L428) | `alert.mp3` |
| `radio_open` | radio_open.mp3 | 0.5 | no | A radio conversation opens | [galaxies/people/conversations/settlement_on_leaving.py:74](../../galaxies/people/conversations/settlement_on_leaving.py#L74), [outpost_report_further.py:41](../../galaxies/people/conversations/outpost_report_further.py#L41), [outpost_report_first.py:42](../../galaxies/people/conversations/outpost_report_first.py#L42) | `radio_open.mp3` |
| `ore_collected` | ore_collected.mp3 | 0.5 | yes | Ore is transferred from a mine to the cargo hold | [spaceships/scanner.py:245](../../spaceships/scanner.py#L245) | `ore_collected.mp3` |
| `mine_placed` | mine_placed.mp3 | 0.8 | yes | A mine is placed | [spaceships/ship.py:556](../../spaceships/ship.py#L556) | `mine_placed.mp3` |
| `bind` | bind.mp3 | 0.5 | no | Arriving at a world (the air roars): notification sound | [spaceships/navigation.py:652](../../spaceships/navigation.py#L652) | `bind.mp3` |
| `unbind` | unbind.mp3 | 0.5 | no | Leaving a world: notification sound | [spaceships/navigation.py:679](../../spaceships/navigation.py#L679) | `unbind.mp3` |
| `time_up` | time_up.wav | 0.4 | no | Time compression raised | [galaxies/people/player.py:136](../../galaxies/people/player.py#L136) | `time_up.wav` |
| `time_down` | time_down.wav | 0.4 | no | Time compression lowered | [galaxies/people/player.py:150](../../galaxies/people/player.py#L150) | `time_down.wav` |
| `game_over` | game_over.wav | 0.7 | no | The death message opens | [galaxies/people/player.py:248](../../galaxies/people/player.py#L248) | `game_over.wav` |
| `laser` | laser.mp3 | 0.3 | yes | Loop: the beam's hum while firing | [spaceships/laser.py:29](../../spaceships/laser.py#L29) (stopped at [line 40](../../spaceships/laser.py#L40)) | `laser.mp3` |
| `laser_on` | laser_on.mp3 | 0.4 | yes | A zap when the beam is switched on | [spaceships/laser.py:25](../../spaceships/laser.py#L25) | `laser_on.mp3` |
| `laser_hit` | laser_hit.wav | 0.3 | yes | Loop: the sizzle of the beam on a rock | [spaceships/laser.py:30](../../spaceships/laser.py#L30) (stopped at [line 41](../../spaceships/laser.py#L41)) | `laser_hit.wav` |
| `thrust` | thrust.wav | 0.25 | yes | Loop: the main thrust | [main.py:589](../../main.py#L589) | `thrust.wav` (also `attitude`) |
| `attitude` | thrust.wav | 0.1 | yes | Loop: the thrust's sound, softer, for yaw, pitch and roll | [main.py:597](../../main.py#L597) | `thrust.wav` (also `thrust`) |
| `scan` | scan.mp3 | 0.3 | yes | Loop: the buzz of the beam scanning an asteroid | [spaceships/scanner.py:253](../../spaceships/scanner.py#L253) (stopped at [lines 284](../../spaceships/scanner.py#L284) and [295](../../spaceships/scanner.py#L295)) | `scan.mp3` |
| `scoop_ice` | scoop_ice.mp3 | 0.3 | yes | Loop: water taken from ice or from an asteroid by the scoop (SPACE held) | [spaceships/ship.py:253](../../spaceships/ship.py#L253) (stopped in [ship.py:229-251](../../spaceships/ship.py#L229) and [main.py:621](../../main.py#L621)) | `scoop_ice.mp3` |
| `scoop_gas` | scoop_gas.mp3 | 0.3 | yes | Loop: the corona or the gas of a giant taken by a probe while it fills | [spaceships/ship.py:312](../../spaceships/ship.py#L312) (set off in the same method, every frame) | `scoop_gas.mp3` |

The rows show which code asks for each sound; the sound itself is a file in `common/resources/sounds`. Line numbers are as
of 2026-11-11.
