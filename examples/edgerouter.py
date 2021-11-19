#!/usr/bin/env python

from mininet.log import setLogLevel
from mininet.node import Node
import docker
import tempfile

def docker_pull_image(image):
    info("Pulling docker image '%s'...\n" % str(image))
    try:
        DockerHost.dcli.images.get(image)
        info("'%s' is already up to date!\n" % str(image))
    except docker.errors.ImageNotFound:
        DockerHost.dcli.images.pull(image)

def docker_create_image_ubunet():
    info("Building docker image 'ubunet'...\n")
    try:
        DockerHost.dcli.images.get("ubunet")
        info("'ubunet' is already up to date!\n")
        return
    except docker.errors.ImageNotFound:
        pass

    docker_pull_image("ubuntu:18.04")

    dockerfile_ubunet = b"""FROM ubuntu:18.04
RUN apt-get update && apt-get install -y --no-install-recommends \
iputils-ping \
iproute2 \
iperf \
net-tools \
&& rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["/bin/bash"]
"""
    with tempfile.TemporaryFile() as tmp:
        tmp.write(dockerfile_ubunet)
        tmp.seek(0)
        DockerHost.dcli.images.build(fileobj=tmp, tag="ubunet")

class LinuxRouter( Node ):
    "A Node with IP forwarding enabled."

    # pylint: disable=arguments-differ
    def config( self, **params ):
        super( LinuxRouter, self).config( **params )
        # Enable forwarding on the router
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )

    def terminate( self ):
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        super( LinuxRouter, self ).terminate()

if __name__ == '__main__':
    import pdb
    import sys
    from functools import partial

    from mininet.examples.dockerhost import DockerHost
    from mininet.net import Mininet
    from mininet.cli import CLI
    from mininet.topo import SingleSwitchTopo
    from mininet.log import setLogLevel
    from mininet.log import info, debug, warn, setLogLevel

    setLogLevel('debug')
    docker_create_image_ubunet()

    DockerHostCustom = partial(
        DockerHost,
        image='ubunet',
    )

    DockerHostVyos = partial(
        DockerHost,
        image='project25/vyos',
    )


    net = Mininet()

    # Setup Controller
    c0 = net.addController( 'c0' )

    # Setup EdgeRouter 
    defaultIP = '192.168.1.1/24'  # IP address for r0-eth1
    vlan2 = '192.168.2.1/24'  # IP address for r0-eth2
    vlan3 = '192.168.3.1/24'  # IP address for r0-eth3
    vlan4 = '192.168.4.1/24'  # IP address for r0-eth4
    # router = net.addHost( 'r0', cls=LinuxRouter, ip=defaultIP )
    router = net.addHost( 'r0', cls=DockerHostVyos, ip=defaultIP, docker_args={"privileged":True} )

    # Setup EdgeRouter Internal Switch
    s0 = net.addSwitch( 's0' )
    net.addLink( s0, router, intfName2='r0-eth1',
                params1={ 'vlan': {'vlan_mode':'trunk', 'trunks':'1'} },
                params2={ 'ip' : defaultIP } )  # for clarity
    net.addLink( s0, router, intfName2='r0-eth2',
                params1={ 'vlan': {'vlan_mode':'trunk', 'trunks':'2'} },
                params2={ 'ip' : vlan2 } )  # for clarity
    net.addLink( s0, router, intfName2='r0-eth3',
                params1={ 'vlan': {'vlan_mode':'trunk', 'trunks':'3'} },
                params2={ 'ip' : vlan3 } )  # for clarity
    net.addLink( s0, router, intfName2='r0-eth4',
                params1={ 'vlan': {'vlan_mode':'trunk', 'trunks':'3'} },
                params2={ 'ip' : vlan4 } )  # for clarity

    # Setup Core Switch
    cs0 = net.addSwitch( 'cs0' )
    # Create a trunk to the internal switches for vlans 2 and 3
    net.addLink( cs0, s0, params2={ 'vlan':{'trunks':'1','vlan_mode':'trunk'} } )

    # Add hosts
    h1 = net.addHost( 'h1', ip='192.168.1.100/24',
                       defaultRoute='via 192.168.1.1' )

    h2_1 = net.addHost( 'h2_1', ip='192.168.2.100/24',
                       defaultRoute='via 192.168.2.1' )

    h2_2 = net.addHost( 'h2_2', ip='192.168.2.101/24',
                       defaultRoute='via 192.168.2.1' )

    h3 = net.addHost( 'h3', ip='192.168.3.104/24',
                       defaultRoute='via 192.168.3.1' )

    net.addLink( h1,   cs0, params2={ 'vlan':{'tag':1,'vlan_mode':'native-tagged'} } )
    net.addLink( h2_1, cs0, params2={ 'vlan':{'tag':2,'vlan_mode':'native-tagged'} } )
    net.addLink( h2_2, cs0, params2={ 'vlan':{'tag':2,'vlan_mode':'native-tagged'} } )
    net.addLink( h3,   cs0 , params2={ 'vlan':{'tag':4,'vlan_mode':'native-tagged'} } )
    # net.addLink( h3,   cs0, params2={ 'vlan':{'tag':3,'vlan_mode':'native-tagged'} } )
    net.start()
    CLI( net )
    net.stop()


