CONFIG = """
provider: 
  name: {provider}
formula: {formula}
scenario: {scenario}
verifier: {verifier}
master_config: {}

grains:
  
instances:
  - name: instance
    box: bandit145/centos_stream9_arm
"""

TOP_SLS = """
base:
  '*':
    - default
"""
