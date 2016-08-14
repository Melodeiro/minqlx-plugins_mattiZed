# minqlx-plugins
This is a collection of plugins that I wrote for Mino's Quake Live Server Mod [minqlx](https://github.com/MinoMino/minqlx). If you run into problems or find any bugs, you can contact me via IRC: [Mino's Channel on Quakenet](http://webchat.quakenet.org/?channels=minqlbot). Look out for "mattiZed" - I may not respond immediately but I will sure read your messages.

Recent versions of queue.py and uneventeams.py are supported by Melodeiro#6341 at Discord, or post your messages at the [SAM support channel](https://discordapp.com/channels/163619179923111937/166341692792766466), or just use [this form](https://github.com/Melodeiro/minqlx-plugins_mattiZed/issues/new) to create a github issue.

## queue.py
This is a queue plugin. Originally written by [mattiZed](https://github.com/mattiZed/minqlx-plugins), now with a whole different mechanics, which should fully replace the old one.

From 2.0 version this plugin implements duel-style queue into the all gametypes. Players receive a status, which is displayed in a round brackets: (s) - spectating, (1..2..n) - position in queue, (AFK) - afk status. For team-based gametypes plugin waits for 2 players before adding them into the game in progress. Also players being added to queue if there is no place in game (due teamsize or locked teams)

* **qlx_queueSetAfkPermission "2"** - minimum permission level for setting afk status to other players
* **qlx_queueAFKTag "^3AFK"** - tag used for the afk status
* **!q** - show all players from queue
* **!afk** - set your status to AFK (spectators only)
* **!here** - remove your AFK status

**NOTE:** for correctly updating the player tags after using the !clan, use the [modified clan.py plugin](https://github.com/Melodeiro/minqlx-plugins_MinoMino/blob/master/clan.py)

## pummel.py
This is a fun plugin.

It displays "Killer x:y Victim" message when Victim gets killed with gauntlet
and stores the information in REDIS DB

Players can display their "pummels" via **!pummel** - this works only for victims
that are on the server at the same time, otherwise we could just spit out
steamIDs.

## uneventeams.py
This plugin takes care of uneven teams.

If uneven teams occur this plugin finds the player who has played the least amount of time since he connected. The information stays persistant over mapchanges etc. In this context playing time means for how long the players have been in a team in an ACTIVE GAME, no matter how long they were alive, though. Keeps timers for 180 seconds, if players disconnected or moved to spectators.

Some parts of this plugin were inspired by this autospec plugin written by [iou(onegirl)](https://github.com/dsverdlo/minqlx-plugins/blob/master/autospec.py), but the decision mechanism that takes care of who will be "punished" is a different approach.

From 1.8 version with non-round-based gametypes support! For full support use with queue.py version 2.0 or later.

* **qlx_unevenTeamsAction "0"** - 0 to slay or 1 to move to spectators when teams are uneven
* **qlx_unevenTeamsMinPlayers "2"** - minimum amount of players in red + blue for uneventeams to work
* **qlx_unevenTeamsActionDelay "15"** - delay (seconds) before excess player will be handled in non round-based gamemodes
* **qlx_unevenTeamsInstantWarning "0"** - if set to 1, don't wait for next round for checking and moving to spectators. Not available for certain gametypes