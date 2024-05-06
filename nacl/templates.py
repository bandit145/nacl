CONFIG = """
provider: 
  name: {provider}
  provider: vmware_desktop
formula: {formula}
scenario: {scenario}
verifier: {verifier}

grains:
  
instances:
  - name: instance
    box: bandit145/centos_stream9_arm
    provider_raw_config_args:
      - 'gui = true'
      - 'vmx["ethernet0.virtualdev"] = "e1000e"'
"""

TOP_SLS = """
base:
  '*':
    - default
"""
