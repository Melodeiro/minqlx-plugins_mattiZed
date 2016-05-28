# This is an extension plugin  for minqlx.
# Copyright (C) 2016 mattiZed (github) aka mattiZed (ql)

# You can redistribute it and/or modify it under the terms of the 
# GNU General Public License as published by the Free Software Foundation, 
# either version 3 of the License, or (at your option) any later version.

# You should have received a copy of the GNU General Public License
# along with minqlx. If not, see <http://www.gnu.org/licenses/>.

# This is a queue plugin written for Mino's Quake Live Server Mod minqlx.
# Some parts of it were inspired by the original queueinfo plugin which was
# written by WalkerX (github) for the old minqlbot.

# The plugin basically shows for how long people have been waiting in spectator
# mode. If a player joins a team, the name is kept for three minutes (so admins
# can track players that dont respect the queue) in the list but now displayed
# with an asterisk to show that the player has left the queue and will soon be
# removed.

# The plugin also features an AFK list, to which players can 
# subscribe/unsubscribe to.

import minqlx
import datetime
import time

_tag_key = "minqlx:players:{}:clantag"

class queue(minqlx.Plugin):
    def __init__(self):
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("team_switch", self.handle_team_switch)
        self.add_hook("set_configstring", self.handle_configstring, priority=minqlx.PRI_LOW)
        self.add_command(("q", "queue"), self.cmd_lq)
        self.add_command("afk", self.cmd_afk)
        self.add_command("here", self.cmd_playing)
        
        self._queue = []
        self._afk   = []
        self._tags  = []
        
        self.set_cvar_once("qlx_queueSetAfkPermission", "2")
        self.set_cvar_once("qlx_queueAFKTag", "^3AFK")
    
    ## Basic List Handling (Queue and AFK)
    def add(self, player, pos=-1):
        '''Safely adds players to the queue'''
        if pos == -1:
            self._queue.append(player)
        else:
            self._queue.insert(pos, player)
    
    def rem(self, player):
        '''Safely removes players from the queue'''
        for p in self._queue:
            if p == player:
                self._queue.remove(p)
    
    def remAFK(self, player):
        '''Safely removes players from afk list'''
        for p in self._afk:
            if p == player:
                self._afk.remove(p)
    
    def posInQueue(self, player):
        '''Returns position of the player in queue'''
        try:
            return self._queue.index(player)
        except ValueError:
            return -1
    
    ## AFK Handling
    def setAFK(self, player):
        '''Returns True if player's state could be set to AFK'''
        if player in self.teams()['spectator']:
            self._afk.append(player)
            return True
        return False
    
    def getTag(self, player):
        '''Sets the player's clantag to AFK, queue number or just (s)'''
        tag_key = _tag_key.format(player.steam_id)
        tag = ""
        if tag_key in self.db:
            tag = self.db[tag_key]
            
        addition = ""
        position = self.posInQueue(player)
        if position > -1:
            addition = position
        elif player in self._afk:
            addition = self.get_cvar("qlx_queueAFKTag")
        elif player in self.teams()['spectator']:
            addition = 's'
        else:
            return tag
        
        if len(tag) > 0 and addition:
            tag = '({}) {}'.format(addition, tag)
        else:
            tag = '({}){}'.format(addition, tag)
        
        return tag
    
    @minqlx.next_frame
    def clAFKTag(self, player):
        '''Sets player's clantag again if there was any'''
        tag_key = _tag_key.format(player.steam_id)
        tag = ""
        if tag_key in self.db:
            tag = self.db[tag_key]
        
        player.clan = tag
    
    ## Plugin Handles and Commands
    def handle_player_disconnect(self, player, reason):
        self.remAFK(player)
        self.rem(player)
    
    def handle_team_switch(self, player, old_team, new_team):
        if new_team != "spectator":
            self.remAFK(player)
            self.clAFKTag(player)
    
    def handle_configstring(self, index, value):
        if not value:
            return
        
        elif 529 <= index < 529 + 64:
            try:
                player = self.player(index - 529)
            except minqlx.NonexistentPlayerError:
                return
                
            
            tag = self.getTag(player)
            
                
            
            cs = minqlx.parse_variables(value, ordered=True)
            cs["xcn"] = tag
            cs["cn"] = tag
            new_cs = "".join(["\\{}\\{}".format(key, cs[key]) for key in cs])
            return new_cs
    
    def cmd_lq(self, player, msg, channel):
        msg = "^7No one in queue."
        if self._queue:
            msg = "^1Queue^7 >> "
            count = 1
            for p in self._queue:
                msg += '{}^7(^3{}^7) '.format(player.name, count)
                count += 1
        channel.reply(msg)
        
        if self._afk:
            msg = "^3Away^7 >> "
            for p in self._afk:
                msg += p.name + " "
            
            channel.reply(msg)
    
    def cmd_afk(self, player, msg, channel):
        if len(msg) > 1:
            if self.db.has_permission(player, self.get_cvar("qlx_queueSetAfkPermission", int)):
                guy = self.find_player(msg[1])[0]
                if self.setAFK(guy):
                    guy.clan = guy.clan # this will start the set_configstring event
                    player.tell("^7Status for {} has been set to ^3AFK^7.".format(guy.name))
                    return minqlx.RET_STOP_ALL
                else:
                    player.tell("Couldn't set status for {} to AFK.".format(guy.name))
                    return minqlx.RET_STOP_ALL
        if self.setAFK(player):
            player.clan = player.clan # this will start the set_configstring event
            player.tell("^7Your status has been set to ^3AFK^7.")
        else:
            player.tell("^7Couldn't set your status to AFK.")

    def cmd_playing(self, player, msg, channel):
        self.remAFK(player)
        self.clAFKTag(player)
        player.tell("^7Your status has been set to ^2AVAILABLE^7.")
