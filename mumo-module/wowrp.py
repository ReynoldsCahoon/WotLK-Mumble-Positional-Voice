#!/usr/bin/env python3
# -*- coding: utf-8

#
# TODO:
# - Channel permission assignment (users shouldn't be allowed to manually move to the proximity channels)
# - Faction separation
# - Death state maybe?
# - Remove empty group channels
#

#
# wowrp.py
# This module automatically moves users to correct channels based on their context
#

import cgi
import base64
import json

from config import commaSeperatedIntegers
from mumo_module import MumoModule

class wowrp(MumoModule):
    default_config = {'wowrp': (
            ('servers', commaSeperatedIntegers, []),
            ('worldmaps', str, '')
        ),
    }

    def __init__(self, name, manager, configuration=None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()
        self.action_poke_user = manager.getUniqueAction()
        self.action_info = manager.getUniqueAction()
        self.action_remove = manager.getUniqueAction()

    def connected(self):
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")

        servers = self.cfg().wowrp.servers
        if not servers:
            servers = manager.SERVERS_ALL

        self.initChannels = False
        self.groupChannelStore = {}
        self.worldChannelStore = {}
        self.sessions = {}
        manager.subscribeServerCallbacks(self, servers)
        manager.subscribeMetaCallbacks(self, servers)

    def disconnected(self): pass

    # module specific code

    def createInitChannels(self, server):
        # create the initial channels and categories
        if len(self.worldChannelStore) == 0:
            # fetch all channels on the server, if we find one named "proximity groups", delete this and all sub-channels.
            # this is important to make sure we keep tabs on all the channel ID's for moving players to the correct channel.
            allChannels = server.getChannels()
            for index in range(len(allChannels)):
                if allChannels[index].name == "Proximity Groups":
                    server.removeChannel(allChannels[index].id)

            # top level channel for all the moderated channels
            pid = server.addChannel("Proximity Groups", 0)

            # waiting room where everyone is muted
            cid = server.addChannel("Waiting Room", pid)
            self.worldChannelStore[-1] = cid

            # category where temporary group channels will be created
            cid = server.addChannel("Group Channels", pid)
            self.worldChannelStore[-2] = cid

            # category for all the continent/overworld channels
            oid = server.addChannel("Overworld", pid)

            # automatically generate world map channels based on config.
            # remove leading and trailing double quotes from the config load function
            maps = eval(self.cfg().wowrp.worldmaps)
            for name, mapId in maps.items():
                cid = server.addChannel(name, oid)
                self.worldChannelStore[mapId] = cid

            # flag initial channel loading as complete so we don't do it again
            self.initChannels = True

    def getChannelByMap(self, mapId):
        # get the channel id associated with the map id from our channel store
        cid = self.worldChannelStore.get(mapId, -1)

        # if no map is found, we fetch the waiting room cid
        if cid == -1:
            cid = self.worldChannelStore.get(cid)

        return cid

    def getOrCreateChannelByLeaderGuid(self, server, guid):
        if not self.groupChannelStore.get(guid):
            # create a new group channel, since one did not exist already
            cid = server.addChannel(str(guid), self.worldChannelStore.get(-2))

            # retrieve the new group channel state and flag it as temporary
            # doesnt work for now, needs more info

            # store the group channel id in our lookup dictionary
            self.groupChannelStore[guid] = cid
            self.log().info("New group channel is: " + str(guid))
            return cid
        else:
            # group channel already existed, so return the channel id
            return self.groupChannelStore.get(guid)

    def update(self, server, state):
        log = self.log()

        # retrieve the parsed context and identity dictionaries
        npc = state.parsedcontext
        npi = state.parsedidentity

        # retrieve the channel id associated with the players' map id
        cid = self.getChannelByMap(npc["map"])

        # if we get the waiting room channel id, we check if the player is in a group
        # if they are, we can assume they are in a dungeon with a party, so we fetch or create a party channel
        if self.worldChannelStore.get(-1) == cid and npi["leaderguid"] > 0:
            cid = self.getOrCreateChannelByLeaderGuid(server, npi["leaderguid"])

        # set the states' channel ID to the new ID and update the player
        state.channel = cid
        server.setState(state)

    def handle(self, server, state):
        def safe_cast(val, to_type, default=None):
            try:
                return to_type(val)
            except (ValueError, TypeError):
                return default

        def verify(mdict, key, vtype):
            if not isinstance(safe_cast(mdict[key], vtype), vtype):
                raise ValueError("'%s' of invalid type" % key)

        # ideally this should be ran on server startup, but eh. this works.
        if not self.initChannels:
            self.createInitChannels(server)

        log = self.log()
        sid = server.id()

        # context is encoded as base64 after mumble 1.3, so decode it.
        state.context = base64.b64decode(state.context)

        # Add defaults for our variables to state
        state.parsedidentity = {}
        state.parsedcontext = {}
        state.is_linked = False

        if sid not in self.sessions:  # Make sure there is a dict to store states in
            self.sessions[sid] = {}

        update = False
        if state.session in self.sessions[sid]:
            # identity or context changed => update
            if state.identity != self.sessions[sid][state.session].identity or \
                state.context != self.sessions[sid][state.session].context:
                update = True
            else:  # id and context didn't change hence the old data must still be valid
                state.is_linked = self.sessions[sid][state.session].is_linked
                state.parsedcontext = self.sessions[sid][state.session].parsedcontext
                state.parsedidentity = self.sessions[sid][state.session].parsedidentity
        else:
            # New user with engaged plugin => update
            if state.identity or state.context:
                self.sessions[sid][state.session] = None
                update = True

        if not update:
            self.sessions[sid][state.session] = state
            return

        # verify that the state update received is from the correct plugin.
        # we only want to process context from our plugin, with the game name as part of the context.
        splitcontext = state.context.split('\0', 1)
        if splitcontext[0] == "World of Warcraft 3.3.5a":
            state.is_linked = True

        if state.is_linked and len(splitcontext) == 2 and state.identity:
            try:
                # make sure to verify context objects are the correct data type
                context = json.loads(splitcontext[1])
                verify(context, "map", int)

                state.parsedcontext = context
            except (ValueError, KeyError, AttributeError) as e:
                log.debug("Invalid context for %s (%d|%d) on server %d: %s", state.name, state.session, state.userid, sid, repr(e))

            try:
                # make sure to verify the identity settings
                identity = json.loads(state.identity)
                verify(identity, "char", str)
                verify(identity, "leaderguid", int)

                state.parsedidentity = identity
            except (KeyError, ValueError) as e:
                log.debug("Invalid identity for %s (%d|%d) on server %d: %s", state.name, state.session, state.userid, sid, repr(e))

            # Update state and remember it
            self.update(server, state)
            self.sessions[sid][state.session] = state

    def userConnected(self, server, state, context=None):
        self.handle(server, state)

    def userStateChanged(self, server, state, context=None):
        self.handle(server, state)

    def userDisconnected(self, server, state, context=None):
        try:
            sid = server.id()
            del self.sessions[sid][state.session]
        except KeyError:
            pass

    def userTextMessage(self, server, user, message, current=None): pass

    def channelCreated(self, server, state, context=None): pass

    def channelRemoved(self, server, state, context=None):
        if state.parent == self.worldChannelStore.get(-2):
            self.log().info("Deleted state name is: " + state.name)
            if len(self.groupChannelStore) > 0:
                self.groupChannelStore.pop(int(state.name))

    def channelStateChanged(self, server, state, context=None): pass

    #
    # --- Meta callback functions
    #

    def started(self, server, context=None):
        self.sessions[server.id()] = {}

    def stopped(self, server, context=None):
        self.sessions[server.id()] = {}