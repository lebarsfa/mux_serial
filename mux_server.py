#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function 
import sys, os
import select, socket, serial

_default_host = '0.0.0.0'
_default_port = 23200
_default_reuse = 1
_default_device = '/dev/ttyS0'
_default_baudrate = 9600
_default_width = serial.EIGHTBITS
_default_parity = serial.PARITY_NONE
_default_stopbits = serial.STOPBITS_ONE
_default_xon = 0
_default_rtc = 0
_default_compat = 0
_default_bufsize = 8192

_READ_ONLY = select.POLLIN | select.POLLPRI

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class MuxServer(object):
	def __init__(self,
				host=_default_host,
				port=_default_port,
                reuse=_default_reuse,
				device = _default_device,
				baudrate=_default_baudrate,
				width = _default_width,
				parity = _default_parity,
				stopbits = _default_stopbits,
				xon = _default_xon,
				rtc = _default_rtc,
                compat = _default_compat,
                bufsize = _default_bufsize,):
		self.host = host
		self.port = port
		self.reuse = reuse
		self.device = device
		self.baudrate = baudrate
		self.width = width
		self.parity = parity
		self.stopbits = stopbits
		self.xon = xon
		self.rtc = rtc
		self.compat = compat
		self.bufsize = bufsize

		self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server.setblocking(0)
		if self.reuse: self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

		self.poller = select.poll()

		self.fd_to_socket = {}
		self.clients = []

	def close(self):
		eprint('\nMUX > Closing...')

		for client in self.clients:
			client.close()
		self.tty.close()
		self.server.close()

		eprint('MUX > Done! =)')

	def add_client(self, client):
		eprint('MUX > New connection from', client.getpeername())
		client.setblocking(0)
		self.fd_to_socket[client.fileno()] = client
		self.clients.append(client)
		self.poller.register(client, _READ_ONLY)

	def remove_client(self, client, why='?'):
		try:
			name = client.getpeername()
		except:
			name = 'client %d' % client.fileno()
		eprint('MUX > Closing', name, ':', why)
		self.poller.unregister(client)
		self.clients.remove(client)
		client.close()

	def run(self):
		try:
			if self.compat: self.tty = serial.Serial(self.device, self.baudrate,
									    self.width, self.parity, self.stopbits,
									    1, 
                                        rtscts=True, dsrdtr=True)
			else: self.tty = serial.Serial(self.device, self.baudrate,
									    self.width, self.parity, self.stopbits,
									    1)
			self.tty.timeout = 0 # Non-blocking
			self.tty.flushInput()
			self.tty.flushOutput()
			self.poller.register(self.tty, _READ_ONLY)
			self.fd_to_socket[self.tty.fileno()] = self.tty
			eprint('MUX > Serial port : %s @ %s' % (self.device, self.baudrate))

			self.server.bind((self.host, self.port))
			self.server.listen(5)
			self.poller.register(self.server, _READ_ONLY)
			self.fd_to_socket[self.server.fileno()] = self.server
			eprint('MUX > Server : %s:%d' % self.server.getsockname())

			eprint('MUX > Use ctrl+c to stop...\n')

			while True:
				clients_status = []
				events = self.poller.poll(500)
				for fd, flag in events:
					# Get socket from fd
					s = self.fd_to_socket[fd]

					if flag & select.POLLHUP:
						clients_status.append((s, 1, 'HUP'))

					elif flag & select.POLLERR:
						clients_status.append((s, 1, 'ERR'))

					elif flag & (_READ_ONLY):
						# A readable server socket is ready to accept a connection
						if s is self.server:
							try:
							    connection, client_host = s.accept()
							    clients_status.append((connection, 2, ''))
							except:
							    eprint('MUX >', 'accept() error')

						# Data from serial port
						elif s is self.tty:
							data = s.read(self.bufsize)
							for client in self.clients:
								try:
								    client.send(data)
								    clients_status.append((client, 0, ''))
								except:
								    clients_status.append((client, 1, 'send() error'))

						# Data from client
						else:
							try:
							    data = s.recv(self.bufsize)
							except:
							    clients_status.append((s, 1, 'recv() error'))
							else:
							    # Client has data
							    if data:
							        self.tty.write(data)
							        clients_status.append((s, 0, ''))
							    # Interpret empty result as closed connection
							    else:
							        clients_status.append((s, 1, 'Got no data'))

				for client, status, msg in clients_status:
					if status == 1:
					    if client in self.clients: 
					        try: self.remove_client(client, msg) 
					        except: eprint('MUX >', 'remove_client() error')
					elif status == 2:
					    self.add_client(client)

		except serial.SerialException as e:
			eprint('\nMUX > Serial error : "%s". Closing...' % e)

		except socket.error as e:
			eprint('\nMUX > Socket error : %s' % e.strerror)

		except (KeyboardInterrupt, SystemExit):
			pass

		finally:
			self.close()

if __name__ == '__main__':
	import optparse

	# Option parsing, duh
	parser = optparse.OptionParser()
	parser.add_option('-d',
					'--device',
					help = 'Serial port device',
					dest = 'device',
					default = _default_device)
	parser.add_option('-b',
					'--baud',
					help = 'Baud rate',
					dest = 'baudrate',
					type = 'int',
					default = _default_baudrate)
	parser.add_option('-i',
					'--ip',
					help = 'Host IP host',
					dest = 'host',
					default = _default_host)
	parser.add_option('-p',
					'--port',
					help = 'Host port',
					dest = 'port',
					type = 'int',
					default = _default_port)
	parser.add_option('-r',
					'--reuse',
					help = 'SO_REUSEADDR socket option',
					dest = 'reuse',
					type = 'int',
					default = _default_reuse)
	parser.add_option('-c',
					'--compat',
					help = 'Compatibility with some virtual serial ports (e.g. created by socat)',
					dest = 'compat',
					type = 'int',
					default = _default_compat)
	parser.add_option('-s',
					'--bufsize',
					help = 'Buffer size',
					dest = 'bufsize',
					type = 'int',
					default = _default_bufsize)
	(opts, args) = parser.parse_args()

	s = MuxServer(host = opts.host,
                port = opts.port,
                reuse = opts.reuse,
				device = opts.device,
				baudrate = opts.baudrate,
				compat = opts.compat,
                bufsize = opts.bufsize)
	s.run()
