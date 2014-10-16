import os
import sys
import argparse

from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.application import internet
from twisted.application.service import MultiService
from twisted.internet.protocol import Protocol, Factory

from smap import util, loader, smapconf
from smap.server import getSite
from smap.util import buildkv


try:
    from smap.ssl import SslServerContextFactory
except ImportError:
    pass

try:
    from smap.bonjour import broadcast
except ImportError:
    print >>sys.stderr, "sMAP: pybonjour not available"
    def broadcast(*args):
        pass



def make_dns_meta(inst):
    root = inst.lookup("/")
    m = {"uuid": str(inst.root_uuid)}
    if root and "Metadata" in root:
        m.update(dict(buildkv("Metadata", root["Metadata"])))
    return m


def RunSMAP():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port",  help="The port sMAP runs on.", default=8080)
    parser.add_argument("-c", "--config", help="The config file to load.", default='../conf/test.ini')
    args = parser.parse_args()
    port = int(args.port)
    config = args.config
    inst = loader.load(config)
    smapconf.start_logging()

    if 'SuggestThreadPool' in smapconf.SERVER:
        reactor.suggestThreadPoolSize(int(smapconf.SERVER['SuggestThreadPool']))

    inst.start()
    from twisted.internet import reactor
    reactor.addSystemEventTrigger('before', 'shutdown', inst.stop)

    site = getSite(inst, docroot=smapconf.SERVER['docroot'])
    service = MultiService()
# add HTTP and HTTPS servers to the twisted multiservice

    meta = make_dns_meta(inst)
    service.addService(internet.TCPServer(port, site))
    broadcast(reactor, "_smap._tcp", port, 'sMAP Server', meta)
    service.startService()
    reactor.run()

if __name__ == '__main__':
    RunSMAP()
