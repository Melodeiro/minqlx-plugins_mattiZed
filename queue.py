# This is an extension plugin  for minqlx.
# Copyright (C) 2016 mattiZed (github) aka mattiZed (ql)
# Copyright (C) 2016 Melodeiro (github)

# You can redistribute it and/or modify it under the terms of the 
# GNU General Public License as published by the Free Software Foundation, 
# either version 3 of the License, or (at your option) any later version.

# You should have received a copy of the GNU General Public License
# along with minqlx. If not, see <http://www.gnu.org/licenses/>.

# This is a queue plugin written for Mino's Quake Live Server Mod minqlx.
# Some parts of it were inspired by the original queueinfo plugin which was
# written by WalkerX (github) for the old minqlbot.

# The plugin put players to the queue when teams are full or even if match in progress.
# When more players adding or there is the place for someone, guys from queue putting to the game.
# 

# The plugin also features an AFK list, to which players can 
# subscribe/unsubscribe to.

# Its the alpha state, so any bugs might happen

# For correctly updating the player tags after using !clan, 
# server needs changed clan.py: http://pastebin.com/3zskZmKb

import minqlx
import datetime
import time
import threading

TEAM_BASED_GAMETYPES = ("ca", "ctf", "dom", "ft", "tdm", "ad", "1f", "har")
NONTEAM_BASED_GAMETYPES = ("ffa", "race", "rr")
_tag_key = "minqlx:players:{}:clantag"

class queue(minqlx.Plugin):
    def __init__(self):
        self.add_hook("player_loaded", self.handle_player_loaded)
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("team_switch", self.handle_team_switch)
        self.add_hook("team_switch_attempt", self.handle_team_switch_attempt)
        self.add_hook("set_configstring", self.handle_configstring, priority=minqlx.PRI_HIGH)
        self.add_hook("client_command", self.handle_client_command)
        self.add_hook("vote_ended", self.handle_vote_ended)
        self.add_hook("new_game", self.handle_new_game)
        self.add_hook("game_end", self.handle_game_end)
        self.add_command(("q", "queue"), self.cmd_lq)
        self.add_command("afk", self.cmd_afk)
        self.add_command("here", self.cmd_playing)
        self.add_command("qversion", self.cmd_qversion)
        self.add_command(("teamsize", "ts"), self.cmd_teamsize, priority=minqlx.PRI_HIGH)
        
        # Commands for debugging
        self.add_command("qpush", self.cmd_qpush, 5)
        self.add_command("qadd", self.cmd_qadd, 5, usage="<size>")
        self.add_command("qupd", self.cmd_qupd, 5)
        
        self.version = "2.3"
        self._queue = []
        self._afk   = []
        self._tags  = {}
        self.initialize()
        self.is_endscreen = False ######## TODO: replace for something better, because 
                                  ######## loading during the endgame screen might cause bugs
        self.set_cvar_once("qlx_queueSetAfkPermission", "2")
        self.set_cvar_once("qlx_queueAFKTag", "^3AFK")
    
    def initialize(self):
        for p in self.players():
            self.updTag(p)
    
    ## Basic List Handling (Queue and AFK)
    @minqlx.thread
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
            self.center_print(player, "You are in the queue to play")
        self.updTag(player)
        self.pushFromQueue()
    
    def remFromQueue(self, player):
        '''Safely removes player from the queue'''
        if player in self._queue:
            self._queue.remove(player)
        for p in self._queue:
            self.updTag(p)
        self.updTag(player)
    
    @minqlx.thread
    def pushFromQueue(self, delay=0):
        '''Check if there is the place and players in queue, and put them in the game'''
        @minqlx.next_frame
        def pushToTeam(amount, team):
            '''Safely put certain amout of players to the selected team'''
            if not self.is_endscreen:
                for count, player in enumerate(self._queue, start=1):
                    if player in self.teams()['spectator']:
                        self._queue.pop(0).put(team)
                    else:
                        self.remFromQueue(player)
                    if count == amount:
                        self.pushFromQueue(0.5)
                        return
                    
        @minqlx.next_frame
        def pushToBoth(times):
            ### TODO ###
            if len(self._queue) > 1 and not self.is_endscreen:
                spectators = self.teams()['spectator']
                if self._queue[0] in spectators:
                    if self._queue[1] in spectators:
                        self._queue.pop(0).put("red")
                        self._queue.pop(0).put("blue")
                    else:
                        self.remFromQueue(self._queue[1])
                else:
                    self.remFromQueue(self._queue[0])
                self.pushFromQueue(0.5)
        
        time.sleep(delay)

        if len(self._queue) == 0:
            return
        if self.game.state != 'in_progress' and self.game.state != 'warmup':
            return
        if self.is_endscreen:
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
            return True
        return False
    
    @minqlx.thread    
    def remTag(self, player):
        if player.steam_id in self._tags:
            del self._tags[player.steam_id]
    
    @minqlx.thread
    def updTag(self, player):
        '''Update the tags dictionary and start the set_configstring event for tag to apply'''
        if player in self.players():
                
            addition = ""
            position = self.posInQueue(player)
            if position > -1:
                addition = '({})'.format(position + 1)
            elif player in self._afk:
                addition = '({})'.format(self.get_cvar("qlx_queueAFKTag"))
            elif player in self.teams()['spectator']:
                addition = '(s)'
                
            self._tags[player.steam_id] = addition
                
            player.clan = player.clan
    
    @minqlx.next_frame
    def center_print(self, player, message):
        minqlx.send_server_command(player.id, "cp \"{}\"".format(message))
    
    ## Plugin Handles and Commands
    def handle_player_disconnect(self, player, reason):
        self.remAFK(player)
        self.remFromQueue(player)
        self.remTag(player)
        self.pushFromQueue(0.5)
    
    def handle_player_loaded(self, player):
        self.updTag(player)
    
    def handle_team_switch(self, player, old_team, new_team):
        if new_team != "spectator":
            self.remFromQueue(player)
            self.remAFK(player)
        else:
            self.updTag(player)
            self.pushFromQueue(0.5)
        
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
        if len(msg) < 2:
            self.addToQueue(player)

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return
            
        self.addToQueue(target_player)
                    
    def cmd_qupd(self, player, msg, channel):
        for p in self.players:
            self.updTag(p)
        
    def cmd_qversion(self, player, msg, channel):
        channel.reply('^3This server has ^5queue.py ^6{} ^3ver. installed.'.format(self.version))
    
    
    
    def handle_client_command(self, player, command):
        @minqlx.thread
        def handler():
            if command == "team s":
                if player in self.teams()['spectator']:
                    self.remFromQueue(player)
                    if player not in self._queue:
                        self.center_print(player, "You are set to spectate only")
    
        handler()
    
    def handle_vote_ended(self, votes, vote, args, passed):
        if vote == "teamsize":
            self.pushFromQueue(4)
                
    def handle_configstring(self, index, value):
        if not value:
            return
        
        elif 529 <= index < 529 + 64:
            try:
                player = self.player(index - 529)
            except minqlx.NonexistentPlayerError:
                return
            
            if player.steam_id in self._tags:
                tag = self._tags[player.steam_id]
                    
                tag_key = _tag_key.format(player.steam_id)
                if tag_key in self.db:
                    if len(tag) > 0:
                        tag += ' '
                    tag += self.db[tag_key]
                    
                    
                cs = minqlx.parse_variables(value, ordered=True)
                cs["xcn"] = tag
                cs["cn"] = tag
                new_cs = "".join(["\\{}\\{}".format(key, cs[key]) for key in cs])
                return new_cs
    
    def handle_new_game(self):
        self.is_endscreen = False
        self.pushFromQueue()
        
    def handle_game_end(self, data):
        self.is_endscreen = True
    
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
        self.pushFromQueue(0.5)
