CONFIG = """
provider: {provider}
formula: {formula}
scenario: {scenario}
verifier: {verifier}

grains:
  
instances:
  - name: box1
    image: quay.io/centos/centos:stream8
    customize: true
    networks:
      - name: net1
      - name: net2
    tmpfs:
      '/run': ''
      '/tmp': ''
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:ro

"""

TOP_SLS = """
base:
  '*':
    - default
"""

DOCKER = """
RUN dnf install -y procps-ng

RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;
VOLUME [ "/sys/fs/cgroup", "/srv/formulas" ]
CMD ["/usr/sbin/init"]
"""
