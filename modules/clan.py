# -*- coding: utf8 -*-
from hon.packets import ID

def setup(bot):
    bot.config.module_config('welcome_members',[1,'Will welcome members in /c m if set to non-zero value'])
    bot.config.module_config('officers', [[], 'Officers alts'])
    bot.config.module_config('allowdnd', [[], 'Allowed to use DND command'])
    bot.dnd = []

def change_member(bot,origin,data):
    who,status,whodid = data[0],data[1],data[2]
    if status == 0:
        del(bot.clan_roster[who])
    elif status == 1:
        if who in bot.clan_roster:
            bot.clan_roster[who]['rank'] = 'Member'
        else:
            bot.clan_roster[who] = {"rank":"Member"}
    elif status == 2:
        bot.clan_roster[who]['rank'] = 'Officer'
    elif status == 3:#not sure about this one
        bot.clan_roster[who]['rank'] = 'Leader'

change_member.event = [ID.HON_SC_CLAN_MEMBER_CHANGE]

def add_member(bot,origin,data):
    id = data[0]
    bot.clan_roster[id] = {"rank":"Member"}
    if bot.config.welcome_members > 0 and id in bot.id2nick:
        nick = bot.id2nick[id]
        bot.write_packet(ID.HON_CS_CLAN_MESSAGE,'Welcome, {0}!'.format(nick))
add_member.event = [ID.HON_SC_CLAN_MEMBER_ADDED]

def member_changestatus(bot,origin,data):
    id = data[0]
    if id in bot.clan_roster:
        bot.clan_status[id] = data[1]
        if data[0] in [ID.HON_STATUS_OFFLINE]:
            for key, nick in enumerate(bot.dnd):
                if id in bot.id2nick and bot.id2nick[id] == nick: 
                    del(bot.dnd[key])
                    break
        if data[1] in [ID.HON_STATUS_ONLINE]:
            """ """
            #nick = bot.id2nick[id]
            #bot.clan_roster[id]['upgrades'] = user_upgrades(bot, nick)
    elif id in bot.id2nick and bot.id2nick[id] == bot.config.owner:
        bot.clan_status[id] = data[1]
member_changestatus.event = [ID.HON_SC_UPDATE_STATUS]

def member_initstatus(bot,origin,data):
    for u in data[1]:
        id = u[0]
        if id in bot.clan_roster:
            if u[1] in [ID.HON_STATUS_ONLINE, ID.HON_STATUS_INGAME]:
                nick = bot.id2nick[id]
                #bot.clan_roster[id]['upgrades'] = user_upgrades(bot, nick)
            bot.clan_status[id] = u[1]
        elif bot.id2nick[id] == bot.config.owner:
            bot.clan_status[id] = u[1]
member_initstatus.event = [ID.HON_SC_INITIAL_STATUS]
member_initstatus.thread = False

def invite(bot,input):
    """invites to clan, admins only""" 
    if not input.admin: return False
    bot.write_packet(ID.HON_CS_CLAN_ADD_MEMBER,input.group(2))
    bot.reply("Invited {0}".format(input.group(2)))
invite.commands = ['invite']

def remove(bot,input):
    """remove from clan, admins only""" 
    if not input.admin: return False
    nick = input.group(2).lower()
    if nick not in bot.nick2id:
        bot.reply('Sorry, I don''t know ' + nick)
    else:
        id = bot.nick2id[nick]
        bot.write_packet(ID.HON_CS_CLAN_REMOVE_MEMBER,id)
        query = { 'f' : 'set_rank', 'target_id' : id, 'member_ck': bot.cookie, 'rank' : 'Remove', 'clan_id' : bot.clan_info['clan_id'] }
        bot.masterserver_request(query)
        bot.reply(nick + " was removed from the clan")
remove.commands = ['remove']

status = {
    ID.HON_STATUS_OFFLINE: "Offline",
    ID.HON_STATUS_ONLINE: "Online",
    ID.HON_STATUS_INLOBBY: "In Lobby",
    ID.HON_STATUS_INGAME: "In Game"
}

def sublist(alist, value):
    return [dictio for dictio in alist if alist[dictio] == value]

def info(bot,input):
    """Get clan member info"""
    if not input.group(2):
        bot.reply( 
            "{0} - Members: {1}, Online: {2}, In-Game: {3}"
            .format(
                bot.clan_info['name'],
                len(bot.clan_roster),
                len(sublist(bot.clan_status, ID.HON_STATUS_ONLINE)),
                len(sublist(bot.clan_status, ID.HON_STATUS_INGAME))
            )
        )
    else:
        nick = input.group(2).lower()
        if nick not in bot.nick2id:
            bot.reply("Unknown Player")
        else:
            id = bot.nick2id[nick]
            if id in bot.clan_roster:
                player = bot.clan_roster[id]
                rank = player['rank']
                query = {'nickname' : nick}
                query['f'] = 'show_stats'
                query['table'] = 'player'
                data = bot.masterserver_request(query,cookie=True)
                bot.reply("{0} - Rank: {1}, Last Online: {2}, Status: {3}".format(nick, rank, data['last_activity'], status[bot.clan_status[id]]))
            else:
                bot.reply("Not in clan")
info.commands = ['info']

def officers(bot, input):
    """Find available officers"""
    avail_officers = []
    for ply in bot.id2nick:
        if ply == bot.account_id:
            continue
        if bot.id2nick[ply] in bot.dnd:
            continue
        if ply in bot.clan_status and ply in bot.clan_roster:
            if bot.clan_status[ply] is ID.HON_STATUS_ONLINE and (bot.clan_roster[ply]['rank'] in ['Officer', 'Leader'] or bot.id2nick[ply] in bot.config.officers):
                avail_officers.append(bot.id2nick[ply])
        elif bot.id2nick[ply] in bot.config.officers:
            if ply in bot.user_status and bot.user_status[ply] is ID.HON_STATUS_ONLINE:
                avail_officers.append(bot.id2nick[ply])
    if len(avail_officers) > 0:
        outstr = ', '.join(avail_officers)
    else:
        outstr = 'None'
    bot.reply( "Available officers: {0}".format( outstr ) )
officers.commands = ['officers']

def officer(bot, input):
    """Add Officer Alt"""
    if not input.admin:
        return officers(bot, input)
    if not input.group(2):
        return
    nick = input.group(2).lower()
    if not nick in bot.config.officers:
        bot.config.set_add('officers', nick)
        bot.reply("Added {0} to officer list".format(nick))
    else:
        bot.reply(nick + " is already an officer")
officer.commands = ['officer']

def unofficer(bot, input):
    """Remove Officer Alt"""
    if not input.admin:
        return False
    if not input.group(2):
        return
    nick = input.group(2).lower()
    if nick in bot.config.officers:
        bot.config.set_del('officers', nick)
        bot.reply("Removed {0} from officer list".format(nick))
    else:
        bot.reply(nick + " isn't an officer")
unofficer.commands = ['unofficer']

def announce(bot, input):
    if not input.admin:
        return False
    if not input.group(2):
        return
    bot.write_packet(ID.HON_CS_CLAN_MESSAGE, input.group(2))
announce.commands = ['announce']

def dnd(bot, input):
    """Users can set themselves to not appear in player listing commands"""
    if input.nick not in bot.nick2id:
        bot.reply("Error occurred")
        return
    id = bot.nick2id[input.nick]
    if not id in bot.clan_roster or (id in bot.clan_roster and not bot.clan_roster[id]['rank'] in ['Officer', 'Leader']):
        if not input.nick in bot.config.officers and not input.nick in bot.config.allowdnd:
            return
    for key, nick in enumerate(bot.dnd):
        if input.nick == nick:
            bot.reply("You are now available.")
            del(bot.dnd[key])
            return
    bot.reply("You are now unavailable.")
    bot.dnd.append(input.nick)
dnd.commands = ['dnd']
