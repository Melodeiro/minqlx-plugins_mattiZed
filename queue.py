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
import threading

TEAM_BASED_GAMETYPES = ("ca", "ctf", "dom", "ft", "tdm", "ad", "1f", "har")
NONTEAM_BASED_GAMETYPES = ("ffa", "race", "rr")
_tag_key = "minqlx:players:{}:clantag"

class queue(minqlx.Plugin):
    def __init__(self):
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("team_switch", self.handle_team_switch)
        self.add_hook("team_switch_attempt", self.handle_team_switch_attempt)
        self.add_hook("set_configstring", self.handle_configstring, priority=minqlx.PRI_LOW)
        self.add_hook("client_command", self.handle_client_command)
        self.add_hook("vote_ended", self.handle_vote_ended)
        self.add_hook("new_game", self.handle_new_game)
        self.add_command(("q", "queue"), self.cmd_lq)
        self.add_command("afk", self.cmd_afk)
        self.add_command("here", self.cmd_playing)
        self.add_command(("teamsize", "ts"), self.cmd_teamsize, 2, usage="<size>", priority=minqlx.PRI_HIGH)
        self.add_command("qpush", self.cmd_qpush, 5)
        self.add_command("qadd", self.cmd_qadd, 5)
        
        self._queue = []
        self._afk   = []
        self._tags  = []
        self.initialize()
        
        self.set_cvar_once("qlx_queueSetAfkPermission", "2")
        self.set_cvar_once("qlx_queueAFKTag", "^3AFK")
    
    def initialize(self):
        for p in self.players():
            self.updTag(p)
    
    ## Basic List Handling (Queue and AFK)
    def addToQueue(self, player, pos=-1):
        '''Safely adds players to the queue'''
        if player not in self._queue:
            if pos == -1:
                self._queue.append(player)
            else:
                self._queue.insert(pos, player)
                for p in self._queue:
                    self.updTag(p)
        if player in self._queue:
            minqlx.send_server_command(player.id, "cp \"You are in the queue to play\"")
        self.updTag(player)
        self.pushFromQueue()
    
    def remFromQueue(self, player):
        '''Safely removes player from the queue'''
        if player in self._queue:
            self._queue.remove(player)
        for p in self._queue:
            self.updTag(p)
    
    @minqlx.thread
    def pushFromQueue(self, delay=0):
        '''Check if there is the place and players in queue, and put them in the game'''
        @minqlx.next_frame
        def pushToTeam(amount, team):
            for count, player in enumerate(self._queue):
                if player in self.teams()['spectator']:
                    self._queue.pop(0).put(team)
                else:
                    self.remFromQueue(player)
                if count == amount - 1:
                    self.pushFromQueue()
                    return
                    
        @minqlx.next_frame
        def pushToBoth(times):
            ### TODO ###
            while len(self._queue) > 1:
                if self._queue[0] in self.teams()['spectator']:
                    if self._queue[1] in self.teams()['spectator']:
                        self._queue.pop(0).put("red")
                        self._queue.pop(0).put("blue")
                    else:
                        self.remFromQueue(self._queue[1])
                else:
                    self.remFromQueue(self._queue[0])
                self.pushFromQueue()
        
        time.sleep(delay)
        if len(self._queue) == 0:
            return
        if self.game.state != 'in_progress' and self.game.state != 'warmup':
            return
            
        ts = int(self.game.teamsize)
        teams = self.teams()
        red_amount = len(teams["red"])
        blue_amount = len(teams["blue"])
        free_amount = len(teams["free"])
        
        #self.msg("DEBUG ts:{} red:{} blue{} free:{}".format(ts, red_amount, blue_amount, free_amount))
        
        if self.game.type_short in TEAM_BASED_GAMETYPES:
            diff = red_amount - blue_amount
            if diff > 0:
                pushToTeam(diff, "blue")
            elif diff < 0:
                pushToTeam(-diff, "red")
            elif len(self._queue) > 1 and red_amount < ts:
                pushToBoth(ts - red_amount) ################ add elo here for those, who want
            elif self.game.state == 'warmup' and red_amount < ts: # for the case if there is 1 player in queue
                pushToTeam(1, "red")
                
        elif self.game.type_short in NONTEAM_BASED_GAMETYPES:
            if free_amount < ts:
                pushToTeam(ts - free_amount, "free")
    
    @minqlx.thread
    def remAFK(self, player):
        '''Safely removes players from afk list'''
        if player in self._afk:
            self._afk.remove(player)
        self.updTag(player)
    
    def posInQueue(self, player):
        '''Returns position of the player in queue'''
        try:
            return self._queue.index(player)
        except ValueError:
            return -1
    
    ## AFK Handling
    def setAFK(self, player):
        '''Returns True if player's state could be set to AFK'''
        if player in self.teams()['spectator'] and player not in self._afk:
            self._afk.append(player)
            self.remFromQueue(player)
            self.updTag(player)
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
            addition = position + 1
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
    
    @minqlx.thread
    def updTag(self, player):
        '''Start the set_configstring event'''
        player.clan = player.clan
    
    ## Plugin Handles and Commands
    #@minqlx.thread <- will cause return warnings
    def handle_player_disconnect(self, player, reason):
        self.remAFK(player)
        self.remFromQueue(player)
        self.pushFromQueue()
    
    #@minqlx.thread
    def handle_team_switch(self, player, old_team, new_team):
        if new_team != "spectator":
            self.remFromQueue(player)
            self.remAFK(player)
        else:
            self.pushFromQueue()
            
    #@minqlx.thread
    def handle_team_switch_attempt(self, player, old_team, new_team):
        if new_team != "spectator" and old_team == "spectator":
            teams = self.teams();
            if len(teams["red"]) == len(teams["blue"]):
                if str(len(teams["red"]) + len(teams["free"])) == self.game.teamsize or self.game.state == 'in_progress':
                    self.remAFK(player)
                    self.addToQueue(player)
                    return minqlx.RET_STOP_ALL
                    
    def cmd_qpush(self, player, msg, channel):
        self.pushFromQueue()
                    
    def cmd_qadd(self, player, msg, channel):
        self.addToQueue(player)
    
    #@minqlx.thread <- will cause return warnings
    def handle_client_command(self, player, command):
        if command == "team s" and player in self.teams()['spectator']:
            self.remFromQueue(player)
            if player not in self._queue:
                minqlx.send_server_command(player.id, "cp \"You are set to spectate only\"")
    
    #@minqlx.thread
    def handle_vote_ended(self, votes, vote, args, passed):
        if vote == "teamsize":
            time.sleep(4)
            self.pushFromQueue()
                
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
    
    def handle_new_game(self):
        self.pushFromQueue()
    
    def cmd_lq(self, player, msg, channel):
        msg = "^7No one in queue."
        if self._queue:
            msg = "^1Queue^7 >> "
            count = 1
            for p in self._queue:
                msg += '{}^7({}) '.format(p.name, count)
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
                    player.tell("^7Status for {} has been set to ^3AFK^7.".format(guy.name))
                    return minqlx.RET_STOP_ALL
                else:
                    player.tell("Couldn't set status for {} to AFK.".format(guy.name))
                    return minqlx.RET_STOP_ALL
        if self.setAFK(player):
            player.tell("^7Your status has been set to ^3AFK^7.")
        else:
            player.tell("^7Couldn't set your status to AFK.")

    def cmd_playing(self, player, msg, channel):
        self.remAFK(player)
        self.updTag(player)
        player.tell("^7Your status has been set to ^2AVAILABLE^7.")
    
    def cmd_teamsize(self, playing, msg, channel):
        self.pushFromQueue(0.1)
