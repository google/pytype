"""Generate code diffs for opcode changes between Python versions.

Automates some of the tedious work of updating pytype to support a new Python
version. This script should be run from the command line as:

  python generate_opcode_diffs.py {old_version} {new_version}

For example, to generate diffs for updating from Python 3.8 to 3.9, use "3.8"
for {old_version} and "3.9" for {new_version}.

Requirements:
* Python 3.7+ to run this script
* Python interpreters for the versions you want to diff

The output has three sections:
* "NEW OPCODES" are new opcode classes that should be added to pyc/opcodes.py.
* "OPCODE MAPPING DIFF" is the content of a dictionary of opcode changes. Just
  copy the python_{major}_{minor}_mapping definition in pyc/opcodes.py for the
  previous version, change the version numbers, and replace the diff - it'll be
  obvious where it goes. Then add the new mapping to the mapping dict in the
  top-level dis function in the same module.
* "OPCODE STUB IMPLEMENTATIONS" are new methods that should be added to vm.py.
If the output contains "NOTE:" lines about modified opcodes, then there are
opcode names that exist in both versions but at different indices. For such
opcodes, the script generates a new class definition for pyc/opcodes.py but does
not generate a new stub implementation for vm.py.
"""

import json
import subprocess
import sys
import tempfile
import textwrap


def generate_diffs(argv):
  """Generate diffs."""
  version1, version2 = argv

  # Create a temporary script to print out information about the opcode mapping
  # of the Python version that the script is running under, and use subprocess
  # to run the script under the two versions we want to diff.
  # opmap is a mapping from opcode name to index, e.g. {'RERAISE': 119}.
  # opname is a sequence of opcode names in which the sequence index corresponds
  # to the opcode index. A name of "<i>" means that i is an unused index.
  with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as f:
    f.write(textwrap.dedent("""
      import dis
      import json
      output = {
        'opmap': dis.opmap,
        'opname': dis.opname,
        'HAVE_ARGUMENT': dis.HAVE_ARGUMENT,
        'HAS_CONST': dis.hasconst,
        'HAS_NAME': dis.hasname,
        'HAS_JREL': dis.hasjrel,
        'HAS_JABS': dis.hasjabs,
        'HAS_LOCAL': dis.haslocal,
        'HAS_FREE': dis.hasfree,
        'HAS_NARGS': dis.hasnargs,
      }
      for attr in dis.__all__:
        if attr.startswith('has'):
          output[attr] = getattr(dis, attr)
      print(json.dumps(output))
    """))
    f.flush()
    proc1 = subprocess.run([f'python{version1}', f.name], capture_output=True,
                           text=True, check=True)
    dis1 = json.loads(proc1.stdout)
    proc2 = subprocess.run([f'python{version2}', f.name], capture_output=True,
                           text=True, check=True)
    dis2 = json.loads(proc2.stdout)

  # Diff the two opcode mappings, generating a change dictionary with entries:
  #   index: ('DELETE', deleted opcode)
  #   index: ('CHANGE', old opcode at this index, new opcode at this index)
  #   index: ('FLAG_CHANGE', opcode)
  #   index: ('ADD', new opcode)
  num_opcodes = len(dis1['opname'])
  assert num_opcodes == len(dis2['opname'])
  changed = {}
  impl_changed = set()
  name_unchanged = set()

  def is_unset(opname_entry):
    return opname_entry == f'<{i}>'

  for i in range(num_opcodes):
    opname1 = dis1['opname'][i]
    opname2 = dis2['opname'][i]
    if opname1 == opname2:
      name_unchanged.add(i)
      continue
    if is_unset(opname2):
      changed[i] = ('DELETE', opname1)
    else:
      if opname2 in dis1['opmap']:
        impl_changed.add(opname2)
      if is_unset(opname1):
        changed[i] = ('ADD', opname2)
      else:
        changed[i] = ('CHANGE', opname1, opname2)

  # Detect flag changes
  for i in name_unchanged:
    for k in set(dis1).union(dis2):
      if not k.startswith('HAS_'):
        continue
      has_flag1 = k in dis1 and i in dis1[k]
      has_flag2 = k in dis2 and i in dis2[k]
      if has_flag1 != has_flag2:
        opname = dis1['opname'][i]
        impl_changed.add(opname)
        changed[i] = ('FLAG_CHANGE', opname)

  # Generate opcode classes.
  classes = []
  for op, diff in sorted(changed.items()):
    if diff[0] == 'DELETE':
      continue
    name = diff[-1]
    flags = []
    if op >= dis2['HAVE_ARGUMENT']:
      cls = [f'class {name}(OpcodeWithArg):']
      flags.append('HAS_ARGUMENT')
    else:
      cls = [f'class {name}(Opcode):']
    for k in dis2:
      if not k.startswith('HAS_'):
        continue
      if op not in dis2[k]:
        continue
      flags.append(k)
    if flags:
      cls.append('  FLAGS = ' + ' | '.join(flags))
    cls.append('  __slots__ = ()')
    classes.append(cls)

  # Generate a mapping diff.
  diffs = []
  for op, diff in sorted(changed.items()):
    if diff[0] == 'DELETE':
      name = diff[1]
      diffs.append(f'{op}: None,  # was {name} in {version1}')
    elif diff[0] == 'CHANGE':
      old_name, new_name = diff[1:]  # pytype: disable=bad-unpacking
      diffs.append(f'{op}: {new_name},  # was {old_name} in {version1}')
    elif diff[0] == 'ADD':
      name = diff[1]
      diffs.append(f'{op}: {name},')
    else:
      assert diff[0] == 'FLAG_CHANGE'

  # Generate stub implementations.
  stubs = []
  for op, diff in sorted(changed.items()):
    if diff[0] == 'DELETE':
      continue
    name = diff[-1]
    if name in impl_changed:
      continue
    stubs.append([f'def byte_{name}(self, state, op):',
                  '  del op',
                  '  return state'])

  return classes, diffs, stubs, sorted(impl_changed)


def main(argv):
  classes, diff, stubs, impl_changed = generate_diffs(argv)
  print('---- NEW OPCODES (pyc/opcodes.py) ----\n')
  print('\n\n\n'.join('\n'.join(cls) for cls in classes))
  if impl_changed:
    print('\nNOTE: Delete the old class definitions for the following '
          'modified opcodes: ' + ', '.join(impl_changed))
  print('\n---- OPCODE MAPPING DIFF (pyc/opcodes.py) ----\n')
  print('    ' + '\n    '.join(diff))
  print('\n---- OPCODE STUB IMPLEMENTATIONS (vm.py) ----\n')
  print('\n\n'.join('  ' + '\n  '.join(stub) for stub in stubs))
  if impl_changed:
    print('\nNOTE: The implementations of the following modified opcodes may '
          'need to be updated: ' + ', '.join(impl_changed))


if __name__ == '__main__':
  main(sys.argv[1:])
