#!/usr/bin/env python

# played around with porting
# http://sourcery.dyndns.org/svn/teensymud/release/tmud-2.0.0/tmud.rb

# YAML implementation:
# http://pyyaml.org/wiki/PyYAMLDocumentation

import random, re, signal, sys
from SocketServer import ThreadingTCPServer, BaseRequestHandler 
import yaml

rand = random.Random()
world = False

AUTHOR = "Jose Nazario"
VERSION = "1.0.0"

BANNER = """

                 This is PunyMUD version %s

             Copyright (C) 2007 by Jose Nazario
             Released under an Artistic License

 Based on TeensyMUD Ruby code Copyright (C) 2005 by Jon A. Lambert
 Original released under the terms of the TeensyMUD Public License


Login> """ % VERSION

HELP = """
===========================================================================
Play commands
  i[nventory] = displays player inventory
  l[ook] = displays the contents of a room
  dr[op] = drops all objects in your inventory into the room
  ex[amine] <object> = examine the named object
  g[get] = gets all objects in the room into your inventory
  k[ill] <name> = attempts to kill player (e.g. k bubba)
  s[ay] <message> = sends <message> to all players in the room
  c[hat] <message> = sends <message> to all players in the game
  h[elp]|?  = displays help
  q[uit]    = quits the game (saves player)
  <exit name> = moves player through exit named (ex. south)
===========================================================================
OLC
  O <object name> = creates a new object (ex. O rose)
  D <object number> = add description for an object
  R <room name> <exit name to> <exit name back> = creates a new room and 
    autolinks the exits using the exit names provided.
    (ex. R Kitchen north south)
===========================================================================
"""

class Obj:
    def __init__(self, name, location):
       self.name = name
       self.location = location
       self.oid = -1
       self.description = None

    def __repr__(self):
	return 'Object: %s (id %s)' % (self.name, self.oid)

class Room(Obj):
    def __init__(self, name):
        self.exits = {}
        self.name = name
	self.oid = -1

    def __repr__(self):
	return 'Room: %s (id %s) - exits %s' % (self.name, self.oid, '|'.join(self.exits.keys()))

class Player(Obj):
    def __init__(self, name, sock=None):
	if sock: self.sock = sock
        self.name = name
        self.location = 1
	self.oid = -1

    def __repr__(self):
	return 'Player: %s (id %s) - at %s' % (self.name, self.oid, self.location)

    def sendto(self, s):
        if getattr(self, 'sock', False): self.sock.send('%s\n' % s)

    def parse(self, m):
	m = m.strip()
        pat = re.compile('(\w+)\W(.*)')
	try:
	    args = pat.findall(m)[0]
	    cmd = args[0]
	    arg = args[1]
	except IndexError:
	    cmd = m
	    arg = False
	if cmd.lower() in [ x.lower() for x in world.find_by_oid(self.location).exits.keys() ]:
	    self.location = world.find_by_oid(self.location).exits[cmd].oid
	    self.parse('look')
        elif cmd.startswith('q'):
	    self.sendto('Bye bye!')
	    del(self.sock)
            world.save()
	elif cmd.lower().startswith('h') or cmd.startswith('?'):
            self.sendto(HELP)
        elif cmd.startswith('i'):
	    for o in world.objects_at_location(self.oid):
		self.sendto(o.name)
	elif cmd.startswith('k'):
	    if not arg: self.parse('help')
	    d = world.find_player_by_name(arg)
	    if d and rand.random() < 0.3:
		world.global_message('%s kills %s' % (self.name, d.name))
		d.sock = None
		world.delete(d)
		world.save()
	    else:
		world.global_message('%s misses' % self.name)
	elif cmd.startswith('s'):
	    if arg: self.sendto(' You say "%s"' % arg)
	    else: self.sendto(' Did you mean to say something?')
	    for x in world.other_players_at_location(self.location, self.oid):
		x.sendto(' %s says "%s"' % (self.name, arg))
	elif cmd.startswith('c'):
	    if arg: self.sendto(' You chat, "%s"' % arg)
	    else: self.sendto(' Did you mean to say something?')
	    world.global_message_others('%s chats, "%s"' % (self.name, arg), self.oid)
	elif cmd.startswith('g'):
	    for q in world.objects_at_location(self.location):
		q.location = self.oid
	    self.sendto('Ok')
	elif cmd.startswith('dr'):
	    for q in world.objects_at_location(self.oid):
		q.location = self.location
	    self.sendto('Ok')
	elif cmd.startswith('ex'):
	    if not arg: self.parse('help')
	    found = False
	    for o in world.objects_at_location(self.oid) + world.objects_at_location(self.location):
		if o.name == arg.strip():
		    if getattr(o, 'description', False): self.sendto(o.description)
		    else: self.sendto("It's just a %s" % o.name)
		    found = True
	    if not found: self.parse('help')
	elif cmd == 'O':
	    if not arg: self.parse('help')
	    try:
		o = Obj(arg.strip(), self.location)
		world.add(o)
		self.sendto('Created object %s' % o.oid)
		world.save()
	    except AttributeError: self.parse('help')
	elif cmd == 'D':
	    if not arg: self.parse('help')
	    try: oid, desc = arg.split(' ', 1)
	    except AttributeError: self.parse('help')
	    try: oid = int(oid)
	    except ValueError: self.parse('help')
	    found = False
	    for o in world.objects_at_location(None):
		if o.oid == oid:
		    o.description = desc
		    world.save()
		    found = True
	    if found: self.sendto('Ok')
	    else: self.sendto('Object %s not found' % oid)
	elif cmd == 'R':
	    if not arg: self.parse('help')
	    tmp = arg.split()
	    if len(tmp) < 3:
		self.sendto(HELP)
	    else:
		name = tmp[0]
		exit_name_to = tmp[1]
		exit_name_back = tmp[2]
		d = Room(name)
		world.find_by_oid(self.location).exits[exit_name_to] = d
		d.exits[exit_name_back] = world.find_by_oid(self.location)
		world.add(d)
		self.sendto('Ok')
		world.save()
	elif cmd.startswith('l'):
	    self.sendto('Room: %s' % world.find_by_oid(self.location).name)
	    if getattr(world.find_by_oid(self.location), 'description', False):
		self.sendto(world.find_by_oid(self.location).description)
	    self.sendto('Players:')
	    for x in world.other_players_at_location(self.location, self.oid):
		if getattr(x, 'sock', False): self.sendto('%s is here' % x.name)
	    self.sendto('Objects:')
	    for x in world.objects_at_location(self.location):
		self.sendto('A %s is here' % x.name)
	    self.sendto('Exits: %s' % ' | '.join(world.find_by_oid(self.location).exits.keys()))
	elif not len(world.find_by_oid(self.location).exits.keys()):
	    self.parse('look')
	else:
	    self.sendto('Huh?')

MINIMAL_DB = """- !!python/object:mud.Room
  exits: {}
  name: Lobby
  oid: 1
"""
class World:
    def __init__(self):
	try:
	    open('db/world.yaml', 'r')
	except IOError:
	    print 'Building minimal world database ...',
	    f = open('db/world.yaml', 'w')
	    f.write(MINIMAL_DB)
	    f.close()
	    print 'Done.'
	print 'Loading world ...',
	self.db =  yaml.load(open('db/world.yaml', 'r'))
	if not isinstance(self.db, list): self.db = [ self.db ]
	self.dbtop = len(self.db)
	print 'Done.'

    def getid(self):
	self.dbtop += 1
	if self.find_by_oid(self.dbtop): self.getid()
	return self.dbtop

    def save(self):
	f = open('db/world.yaml', 'w')
	f.write(yaml.dump(self.db))
	f.close()

    def add(self, obj):
	obj.oid = self.getid()
	self.db.insert(int(obj.oid), obj)

    def delete(self, obj):
	self.db.remove(obj)

    def find_player_by_name(self, nm):
	for o in self.db:
	    if isinstance(o, Player) and o.name == nm:
		return o

    def players_at_location(self, loc):
	l = []
	for o in self.db:
	    if isinstance(o, Player):
		if loc and o.location == loc:
		    l.append(o)
		else: l.append(o)
	return l

    def other_players_at_location(self, loc, plrid):
	l = []
	for o in self.db:
	    if isinstance(o, Player) and o.oid != plrid:
		if loc and o.location == loc:
		    l.append(o)
		elif not loc: l.append(o)
	return l

    def global_message(self, msg):
	for plr in self.players_at_location(None):
	    try: plr.sendto(msg)
	    except: print 'Error sending "%s" to %s' % (msg, plr.name)

    def global_message_others(self, msg, plrid):
	for plr in self.other_players_at_location(None, plrid):
	    plr.sendto(msg)

    def objects_at_location(self, loc):
	l = []
	for o in self.db:
	    if isinstance(o, Obj) and not isinstance(o, Room) and not isinstance(o, Player):
		if loc and o.location == loc: l.append(o)
		elif not loc: l.append(o)
	return l

    def find_by_oid(self, i):
	for x in self.db:
	    if x.oid == i: return x
	return None

class MudHandler(BaseRequestHandler):
    def setup(self):
        self.request.send(BANNER)
	login_name = self.request.recv(1024).strip()
	if len(login_name) < 1: self.setup()
	d = world.find_player_by_name(login_name)
	if d:
	    d.sock = self.request
	else:
	    d = Player(login_name, self.request)
	    world.add(d)
	d.sendto('Welcome %s @ %s' % (d.name, self.client_address[0]))
	r = 'look'
	while r:
	    d.parse(r)
	    if not getattr(d, 'sock', False): break
	    d.sock.send('> ')
	    r = self.request.recv(1024)
	self.finish()

def main():
    global world
    world = World()
    cont = True

    """
    def shutdown(num, frame):
	world.global_message('World is shutting down')
	for plr in world.players_at_location(None):
	    try: plr.parse('quit')
	    except: print 'ERROR: %s could not quit gracefully' % plr.name
	world.save()
	sys.exit()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    """

    z = ThreadingTCPServer(('', 4000), MudHandler)
    while True:
        try: z.handle_request()
        except KeyboardInterrupt: break
    for plr in world.players_at_location(None):
        try: plr.parse('quit')
	except: print 'ERROR: %s could not quit gracefully' % plr.name
    world.save()

if __name__ == '__main__':
    main()
